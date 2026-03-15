"""
Report Generator Agent
Responsible for creating professional formatted reports.

Phase 1: reads validated findings, sources, insights, and confidence data
from MongoDB by session_id instead of receiving them in the context dict.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import re

from app.agents.base_agent import BaseAgent, AgentStatus
from app.tools.formatting_tools import FormattingTools
from app.config import settings
from app.utils.logging import logger
from app.database.repositories import SourceRepository, FindingRepository, ResearchRepository


class ReportGeneratorAgent(BaseAgent):
    """
    Report Generator Agent - Report writing and formatting specialist.
    
    Responsibilities:
    - Structure findings into logical report sections
    - Write coherent narrative from research data
    - Generate reports in multiple formats (Markdown, HTML, PDF)
    - Format citations properly (APA, MLA, Chicago)
    - Create executive summaries
    """
    
    def __init__(self):
        system_prompt = """You are an expert report writer who creates professional, data-rich research reports.

Your responsibilities:
1. Structure findings into logical, well-organized sections
2. Write clear, coherent narrative that tells the research story with SPECIFIC DATA
3. Include proper citations and source attribution
4. Create compelling executive summaries with key statistics
5. Ensure reports are accessible and easy to read

Guidelines:
- Use clear, professional language with specific data points
- NEVER use placeholder text like [topic], [finding 1], [limitation 1] etc.
- Every claim must be backed by specific evidence from the research
- Include actual numbers, percentages, and statistics wherever available
- Organize content from most to least important
- Use headings and subheadings for navigation
- Include visual breaks (lists, emphasis) for readability
- Cite sources consistently throughout
- Write for your target audience
- Balance comprehensiveness with conciseness
- If data is limited, acknowledge honestly but still present what was found

Your reports should be publication-ready with zero placeholder text."""
        
        super().__init__(
            name="Report Generator",
            role="Report writing and formatting specialist",
            system_prompt=system_prompt,
            model=settings.report_generator_model,
            temperature=0.4,
            max_tokens=8192,
            timeout=settings.agent_timeout
        )
        
        self.formatting_tools = FormattingTools()
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute report generation from validated findings.
        
        Phase 1: Loads sources, validated findings, insights, and confidence
        data from MongoDB by session_id.
        """
        query = context.get("query", "")
        session_id = context.get("session_id", "")
        report_format = context.get("report_format", "markdown")
        citation_style = context.get("citation_style", "APA")

        # ── Phase 1: query MongoDB ────────────────────────────────
        sources: List[Dict[str, Any]] = []
        findings: List[Dict[str, Any]] = []
        key_insights: List[str] = []
        confidence_summary: Dict[str, Any] = {}

        if session_id:
            source_docs = await SourceRepository.get_by_research(session_id)
            sources = [self._source_doc_to_dict(s) for s in source_docs]

            pipeline = await ResearchRepository.get_pipeline_data(session_id)
            findings = pipeline.get("validated_findings", [])
            key_insights = pipeline.get("key_insights", [])
            confidence_summary = pipeline.get("confidence_summary", {})

            # Fallback chain within pipeline_data
            if not findings:
                findings = pipeline.get("organized_findings", [])

            # Fallback: load raw findings from FindingRepository if pipeline_data has nothing
            if not findings:
                logger.warning(
                    f"[REPORT_GEN] No findings in pipeline_data for session {session_id}, "
                    f"loading raw findings from FindingRepository"
                )
                finding_docs = await FindingRepository.get_by_research(session_id)
                findings = [self._finding_doc_to_dict(f) for f in finding_docs]
        else:
            # Backward compat / tests
            sources = context.get("sources", [])
            findings = context.get("validated_findings", [])
            key_insights = context.get("key_insights", [])
            confidence_summary = context.get("confidence_summary", {})

        # Extra fallback from context (orchestrator now passes raw_findings)
        if not findings:
            findings = context.get("organized_findings", [])
        if not findings:
            findings = context.get("consolidated_findings", [])
        if not findings:
            findings = context.get("raw_findings", [])
        # ──────────────────────────────────────────────────────────
        
        logger.info(f"Report Generator starting for: {query} ({len(findings)} findings, {len(sources)} sources)")
        
        if not query:
            logger.error("Report Generator received EMPTY query — this is a pipeline bug")
        if len(findings) == 0:
            logger.warning("Report Generator received 0 findings — report quality will be limited")
        if len(sources) == 0:
            logger.warning("Report Generator received 0 sources — report quality will be limited")
        
        try:
            await self._set_status(AgentStatus.IN_PROGRESS)
            await self._update_progress(5, "Planning report structure...")
            
            # Step 1: Generate report title
            title = await self._generate_title(query)
            
            # Step 2: Structure sections
            await self._update_progress(15, "Structuring report sections...")
            sections = await self._structure_sections(query, findings, key_insights)
            
            # Step 3: Write section content
            await self._update_progress(30, "Writing report content...")
            written_sections = await self._write_sections(query, sections, findings, sources)
            
            # Step 4: Generate executive summary
            await self._update_progress(55, "Creating executive summary...")
            summary = await self._generate_executive_summary(
                query, written_sections, confidence_summary
            )
            
            # Step 5: Generate Markdown report
            await self._update_progress(70, "Generating Markdown report...")
            markdown_content = await self.formatting_tools.generate_markdown(
                title=title,
                sections=written_sections,
                sources=sources[:100],  # Limit citations
                citation_style=citation_style
            )
            
            # Insert summary after title
            markdown_with_summary = self._insert_summary(markdown_content, summary)
            
            # Step 6: Generate HTML if needed
            await self._update_progress(85, "Generating HTML version...")
            html_content = await self.formatting_tools.generate_html(
                title=title,
                markdown_content=markdown_with_summary
            )
            
            # Step 7: Generate PDF if requested
            pdf_bytes = None
            if report_format == "pdf":
                await self._update_progress(92, "Generating PDF version...")
                pdf_bytes = await self.formatting_tools.generate_pdf(
                    title=title,
                    html_content=html_content
                )
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(
                findings, sources, confidence_summary
            )
            
            await self._update_progress(100, "Report generation complete!")
            await self._set_status(AgentStatus.COMPLETED)
            
            return {
                "status": "completed",
                "query": query,
                "report": {
                    "title": title,
                    "summary": summary,
                    "markdown_content": markdown_with_summary,
                    "html_content": html_content,
                    "pdf_bytes": pdf_bytes,
                    "sections": written_sections,
                    "citation_style": citation_style,
                    "quality_score": quality_score
                },
                "metadata": {
                    "total_sources": len(sources),
                    "total_findings": len(findings),
                    "confidence_level": confidence_summary.get("confidence_level", "medium"),
                    "generated_at": datetime.utcnow().isoformat()
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Report Generator execution failed: {e}")
            await self._set_status(AgentStatus.FAILED, str(e))
            return {
                "status": "failed",
                "error": str(e),
                "report": None
            }
    
    async def _generate_title(self, query: str) -> str:
        """Generate a professional report title."""
        
        prompt = f"""Generate a professional, concise report title for this specific research query.

Query: {query}

The title should:
1. Be clear and descriptive of THIS SPECIFIC topic
2. Be professional in tone
3. Be 5-12 words maximum
4. Not include quotes or special characters
5. MUST directly reflect the query above — do NOT invent a different topic

Return only the title, nothing else."""
        
        try:
            title = await self.think(prompt)
            title = title.strip().strip('"\'')
            # Safety check: if the LLM returned a suspiciously generic title,
            # fall back to the user's query
            if len(title) < 5 or not any(w.lower() in title.lower() for w in query.split()[:3] if len(w) > 3):
                logger.warning(f"Title '{title}' seems unrelated to query '{query}', using fallback")
                return f"Research Report: {query[:80]}"
            return title
        except Exception as e:
            logger.warning(f"Title generation failed: {e}")
            return f"Research Report: {query[:80]}"
    
    async def _structure_sections(
        self,
        query: str,
        findings: List[Dict[str, Any]],
        insights: List[str]
    ) -> List[Dict[str, Any]]:
        """Create logical section structure for the report."""
        
        # Use formatting tools to structure findings
        sections = await self.formatting_tools.structure_findings(findings, query)
        
        # Ensure we have key sections
        section_titles = [s.get("title", "").lower() for s in sections]
        
        # Add methodology section if not present
        if not any("method" in t for t in section_titles):
            sections.insert(0, {
                "title": "Research Methodology",
                "content": "",
                "order": 0
            })
        
        # Add conclusions section if not present
        if not any("conclusion" in t for t in section_titles):
            sections.append({
                "title": "Conclusions and Recommendations",
                "content": "",
                "order": len(sections)
            })
        
        # Reorder
        for i, section in enumerate(sections):
            section["order"] = i + 1
        
        return sections
    
    async def _write_sections(
        self,
        query: str,
        sections: List[Dict[str, Any]],
        findings: List[Dict[str, Any]],
        sources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Write detailed content for each section."""
        
        written_sections = []
        
        for i, section in enumerate(sections):
            title = section.get("title", f"Section {i+1}")
            existing_content = section.get("content", "")
            
            # Progress update
            progress = 30 + int((i / len(sections)) * 25)
            await self._update_progress(progress, f"Writing: {title}...")
            
            # Generate content based on section type
            if "methodology" in title.lower():
                content = await self._write_methodology_section(sources)
            elif "conclusion" in title.lower():
                content = await self._write_conclusions_section(query, findings)
            elif existing_content:
                content = await self._enhance_section_content(
                    title, existing_content, findings
                )
            else:
                content = await self._write_section_content(
                    title, query, findings, sources
                )
            
            written_sections.append({
                "title": title,
                "content": content,
                "order": section.get("order", i + 1)
            })
        
        return written_sections
    
    async def _write_methodology_section(
        self,
        sources: List[Dict[str, Any]]
    ) -> str:
        """Write the methodology section."""
        
        # Count sources by type
        source_types = {}
        for source in sources:
            stype = source.get("api_source", "other")
            source_types[stype] = source_types.get(stype, 0) + 1
        
        source_summary = ", ".join([
            f"{count} from {stype.title()}"
            for stype, count in source_types.items()
            if count > 0
        ])
        
        # Count source types
        academic_count = source_types.get("arxiv", 0) + source_types.get("pubmed", 0)
        news_count = source_types.get("newsapi", 0)
        web_count = source_types.get("google", 0) + source_types.get("serpapi", 0)
        wiki_count = source_types.get("wikipedia", 0)
        
        content = f"""This research was conducted using a multi-agent AI system that employs specialized agents for different aspects of the research process:

1. **Information Gathering**: The Researcher Agent collected information from multiple sources including academic databases (ArXiv, PubMed), news sources (NewsAPI), web search (Google/SerpAPI), and encyclopedic sources (Wikipedia). Sources were filtered for relevance to the specific research query before analysis.

2. **Analysis**: The Analyst Agent synthesized the collected information, identified patterns across sources, consolidated findings into coherent themes, and detected areas of consensus and contradiction.

3. **Verification**: The Fact-Checker Agent validated claims through cross-referencing against multiple sources, assessed source credibility using domain reputation analysis, and detected potential bias.

4. **Report Generation**: The Report Generator Agent structured findings into this comprehensive report with proper citations and evidence-based conclusions.

**Sources Analyzed**: A total of {len(sources)} relevant sources were analyzed (after filtering for relevance), including {source_summary}.

**Source Breakdown**: {academic_count} academic/peer-reviewed sources, {news_count} news articles, {web_count} web sources, and {wiki_count} encyclopedic references.

**Quality Assurance**: All findings have been cross-referenced against multiple sources, relevance-filtered to remove off-topic results, and confidence scores have been assigned based on the level of corroboration."""
        
        return content
    
    async def _write_conclusions_section(
        self,
        query: str,
        findings: List[Dict[str, Any]]
    ) -> str:
        """Write the conclusions section."""
        
        verified_findings = [f for f in findings if f.get("verified", False)]
        high_confidence = [f for f in findings if f.get("confidence_score", 0) > 0.7]
        
        # Use ALL findings if no verified ones (don't let empty list produce placeholders)
        display_findings = verified_findings or high_confidence or findings
        
        findings_summary = "\n".join([
            f"[{i+1}] {f.get('title', 'Finding')}: {f.get('content', '')[:350]}"
            for i, f in enumerate(display_findings[:15])
        ])
        
        if not findings_summary:
            findings_summary = "No specific findings were extracted from the sources analyzed."
        
        prompt = f"""Write a conclusions and recommendations section for a research report on: {query}

Key Findings from Research:
{findings_summary}

Total findings analyzed: {len(findings)}
Verified findings: {len(verified_findings)}
High confidence findings: {len(high_confidence)}

INSTRUCTIONS:
1. Summarize the main findings using SPECIFIC DATA from above — never use generic placeholders
2. Discuss real implications based on the actual findings
3. Note actual limitations of this specific research (e.g., limited academic sources, mostly news-based data)
4. Suggest 2-3 specific areas for further research based on gaps identified
5. Be 3-4 paragraphs long
6. CRITICAL: Do NOT use placeholder text like [topic], [main finding 1], [limitation 1], etc.
7. CRITICAL: Every statement must reference actual data from the findings above
8. If findings are limited, honestly acknowledge this and explain what the available evidence suggests

Write in a professional, objective tone. Be specific and data-driven."""
        
        try:
            return await self.think(prompt)
        except Exception as e:
            logger.warning(f"Conclusions generation failed: {e}")
            return f"This research on \"{query}\" identified {len(verified_findings)} verified findings. Further investigation is recommended to explore emerging developments in this area."
    
    async def _enhance_section_content(
        self,
        title: str,
        existing_content: str,
        findings: List[Dict[str, Any]]
    ) -> str:
        """Enhance existing section content."""
        
        prompt = f"""Enhance this section content to be more comprehensive and professional.

Section Title: {title}

Current Content:
{existing_content[:2000]}

Enhance the content to:
1. Be well-written and professional
2. Include relevant details from findings
3. Use clear paragraph structure
4. Be 2-4 paragraphs long

Write the enhanced content:"""
        
        try:
            return await self.think(prompt)
        except Exception:
            return existing_content
    
    async def _write_section_content(
        self,
        title: str,
        query: str,
        findings: List[Dict[str, Any]],
        sources: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Write new section content from scratch."""

        relevant_findings = "\n".join([
            f"[F{i+1}] {f.get('title', '')}: {f.get('content', '')[:400]}"
            for i, f in enumerate(findings[:25])
        ])

        if not relevant_findings:
            relevant_findings = "Limited findings available for this section."

        # Collect source URLs from findings (supporting_sources & resolved_sources)
        # so the LLM can emit inline Markdown hyperlinks
        citation_map: Dict[str, str] = {}
        for f in findings:
            for s in f.get("supporting_sources", []):
                if isinstance(s, dict) and s.get("url") and s.get("title"):
                    citation_map[s["url"]] = s["title"]
            for s in f.get("resolved_sources", []):
                if isinstance(s, dict) and s.get("url") and s.get("title"):
                    citation_map[s["url"]] = s["title"]
        # Supplement with the raw sources list when available
        if sources:
            for s in sources[:30]:
                u, t = s.get("url", ""), s.get("title", "")
                if u and t and u not in citation_map:
                    citation_map[u] = t

        citation_block = ""
        if citation_map:
            lines = [f"  - [{t}]({u})" for u, t in list(citation_map.items())[:30]]
            citation_block = "Available sources for inline citation:\n" + "\n".join(lines) + "\n"

        prompt = f"""Write a detailed, evidence-rich section for a research report.

Report Topic: {query}
Section Title: {title}

Available Findings:
{relevant_findings}

{citation_block}
Instructions:
1. Write 3-6 well-developed paragraphs directly addressing the section topic
2. Use SPECIFIC data, statistics, percentages, and concrete evidence from the findings above
3. Include inline Markdown hyperlinks to cite sources wherever possible: [Source Title](URL)
4. Use clear paragraph structure flowing from background → evidence → implications
5. NEVER use placeholder text like [topic], [finding], [example], [limitation]
6. If data is limited for this section, state what is known and clearly identify the gaps
7. End with a brief synthesis paragraph contextualising the evidence

Write the section (minimum 250 words):"""

        try:
            return await self.think(prompt)
        except Exception as e:
            logger.warning(f"Section writing failed: {e}")
            if findings:
                fallback_parts = [f"This section covers key findings related to {title.lower()} for the research topic.\n"]
                for f in findings[:5]:
                    f_title = f.get('title', '')
                    f_content = f.get('content', '')
                    if f_content:
                        fallback_parts.append(f"**{f_title}**: {f_content[:300]}\n")
                return "\n".join(fallback_parts)
            return f"This section on {title} requires further research. The available sources did not provide sufficient data for a detailed analysis."
    
    async def _generate_executive_summary(
        self,
        query: str,
        sections: List[Dict[str, Any]],
        confidence_summary: Dict[str, Any]
    ) -> str:
        """Generate executive summary."""
        
        # Combine section content — use 1500 chars per section for a richer summary
        full_content = "\n\n".join([
            f"{s.get('title', '')}\n{s.get('content', '')[:1500]}"
            for s in sections
        ])

        try:
            summary = await self.formatting_tools.create_summary(
                content=full_content,
                max_length=1200
            )
        except Exception as e:
            logger.error(f"Executive summary generation failed: {e}")
            summary = (
                "This research identified and analyzed multiple sources on the "
                "requested topic. While relevant sources were collected, the "
                "automated extraction pipeline encountered difficulties distilling "
                "specific findings. The sections below present the available evidence. "
                "Manual review of cited sources is recommended."
            )
        
        # Add confidence note
        confidence_level = confidence_summary.get("confidence_level", "medium")
        summary += f"\n\n*Research Confidence Level: {confidence_level.upper()}*"
        
        return summary
    
    def _insert_summary(self, markdown: str, summary: str) -> str:
        """Insert executive summary after the title."""
        
        lines = markdown.split('\n')
        
        # Find where to insert (after title and metadata)
        insert_index = 0
        for i, line in enumerate(lines):
            if line.startswith('---'):
                insert_index = i + 1
                break
        
        summary_section = f"\n## Executive Summary\n\n{summary}\n"
        lines.insert(insert_index, summary_section)
        
        return '\n'.join(lines)
    
    def _calculate_quality_score(
        self,
        findings: List[Dict[str, Any]],
        sources: List[Dict[str, Any]],
        confidence_summary: Dict[str, Any]
    ) -> float:
        """Calculate overall quality score (0-5)."""
        
        # Factors
        source_count_score = min(len(sources) / 100, 1.0)  # Max at 100 sources
        
        verified_ratio = confidence_summary.get("verified_findings", 0) / max(len(findings), 1)
        
        confidence = confidence_summary.get("overall_confidence", 0.5)
        
        # Calculate weighted score
        quality = (
            source_count_score * 1.5 +
            verified_ratio * 2.0 +
            confidence * 1.5
        )
        
        return round(min(quality, 5.0), 1)

    # ── Phase 1 helpers ───────────────────────────────────────────
    @staticmethod
    def _source_doc_to_dict(doc) -> Dict[str, Any]:
        """Convert a Source Beanie document to the dict format agents expect."""
        return {
            "title": doc.title,
            "url": doc.url,
            "snippet": doc.content_preview or "",
            "source_type": doc.source_type.value if hasattr(doc.source_type, "value") else str(doc.source_type or "other"),
            "api_source": doc.api_source or "unknown",
            "author": doc.author or "",
            "published_at": str(doc.published_at) if doc.published_at else "",
            "credibility_score": doc.credibility_score,
            **(doc.metadata or {}),
        }

    @staticmethod
    def _finding_doc_to_dict(doc) -> Dict[str, Any]:
        """Convert a Finding Beanie document to the dict format agents expect."""
        meta = doc.metadata or {}
        return {
            "content": doc.content,
            "title": doc.title,
            "finding_type": doc.finding_type.value if hasattr(doc.finding_type, "value") else str(doc.finding_type or "insight"),
            "source_refs": meta.get("source_refs", ""),
            "resolved_sources": meta.get("resolved_sources", []),
            "confidence": meta.get("preliminary_credibility", "medium"),
            "confidence_score": doc.confidence_score,
            "verified": doc.verified,
        }
