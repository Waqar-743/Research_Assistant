"""
Formatting Tools for the Report Generator Agent.
Handles Markdown, HTML, and PDF generation with citations.
"""

import re
from typing import List, Dict, Any, Optional
from datetime import datetime
import markdown
from io import BytesIO

from app.config import settings
from app.utils.logging import logger
from app.tools.llm_tools import LLMTools


class FormattingTools:
    """Collection of formatting tools for report generation."""
    
    def __init__(self):
        self.llm = LLMTools()
    
    async def generate_markdown(
        self,
        title: str,
        sections: List[Dict[str, Any]],
        sources: List[Dict[str, Any]],
        citation_style: str = "APA"
    ) -> str:
        """
        Generate a well-formatted Markdown report.
        
        Args:
            title: Report title
            sections: List of sections with title and content
            sources: List of sources for citations
            citation_style: Citation format (APA, MLA, Chicago)
            
        Returns:
            Formatted Markdown string
        """
        logger.info(f"Generating Markdown report: {title}")
        
        md_parts = []
        
        # Title
        md_parts.append(f"# {title}\n")
        
        # Metadata
        md_parts.append(f"*Generated on {datetime.utcnow().strftime('%B %d, %Y at %H:%M UTC')}*\n")
        md_parts.append(f"*{len(sources)} sources analyzed*\n")
        md_parts.append("---\n")
        
        # Table of Contents
        md_parts.append("## Table of Contents\n")
        for i, section in enumerate(sections, 1):
            section_title = section.get("title", f"Section {i}")
            anchor = section_title.lower().replace(" ", "-").replace(".", "")
            md_parts.append(f"{i}. [{section_title}](#{anchor})\n")
        md_parts.append(f"{len(sections) + 1}. [References](#references)\n")
        md_parts.append("---\n")
        
        # Sections
        for section in sections:
            section_title = section.get("title", "Untitled Section")
            section_content = section.get("content", "")
            
            md_parts.append(f"## {section_title}\n")
            md_parts.append(f"{section_content}\n")
            
            # Add subsections if present
            for subsection in section.get("subsections", []):
                sub_title = subsection.get("title", "")
                sub_content = subsection.get("content", "")
                md_parts.append(f"### {sub_title}\n")
                md_parts.append(f"{sub_content}\n")
            
            md_parts.append("\n")
        
        # References section
        md_parts.append("---\n")
        md_parts.append("## References\n")
        
        citations = await self.format_citations(sources, citation_style)
        md_parts.append(citations)
        
        return "\n".join(md_parts)
    
    async def generate_html(
        self,
        title: str,
        markdown_content: str
    ) -> str:
        """
        Generate HTML report from Markdown content.
        
        Args:
            title: Report title
            markdown_content: Markdown formatted content
            
        Returns:
            HTML string
        """
        logger.info(f"Generating HTML report: {title}")
        
        # Convert Markdown to HTML
        html_body = markdown.markdown(
            markdown_content,
            extensions=[
                'tables',
                'fenced_code',
                'codehilite',
                'toc',
                'nl2br'
            ]
        )
        
        # Wrap in HTML template
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --primary-blue: #2563EB;
            --secondary-purple: #7C3AED;
            --text-primary: #111827;
            --text-secondary: #6B7280;
            --bg-white: #FFFFFF;
            --bg-gray: #F3F4F6;
            --border-color: #E5E7EB;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: var(--text-primary);
            background-color: var(--bg-gray);
            padding: 2rem;
        }}
        
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: var(--bg-white);
            padding: 3rem;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        
        h1 {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary-blue);
            margin-bottom: 1rem;
            border-bottom: 3px solid var(--primary-blue);
            padding-bottom: 0.5rem;
        }}
        
        h2 {{
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-top: 2rem;
            margin-bottom: 1rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.5rem;
        }}
        
        h3 {{
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--secondary-purple);
            margin-top: 1.5rem;
            margin-bottom: 0.75rem;
        }}
        
        p {{
            margin-bottom: 1rem;
            color: var(--text-primary);
        }}
        
        ul, ol {{
            margin-bottom: 1rem;
            padding-left: 2rem;
        }}
        
        li {{
            margin-bottom: 0.5rem;
        }}
        
        a {{
            color: var(--primary-blue);
            text-decoration: none;
        }}
        
        a:hover {{
            text-decoration: underline;
        }}
        
        blockquote {{
            border-left: 4px solid var(--secondary-purple);
            padding-left: 1rem;
            margin: 1rem 0;
            color: var(--text-secondary);
            font-style: italic;
        }}
        
        code {{
            background: var(--bg-gray);
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9em;
        }}
        
        pre {{
            background: var(--bg-gray);
            padding: 1rem;
            border-radius: 8px;
            overflow-x: auto;
            margin-bottom: 1rem;
        }}
        
        pre code {{
            background: none;
            padding: 0;
        }}
        
        hr {{
            border: none;
            border-top: 1px solid var(--border-color);
            margin: 2rem 0;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1rem;
        }}
        
        th, td {{
            border: 1px solid var(--border-color);
            padding: 0.75rem;
            text-align: left;
        }}
        
        th {{
            background: var(--bg-gray);
            font-weight: 600;
        }}
        
        .metadata {{
            color: var(--text-secondary);
            font-size: 0.9rem;
            margin-bottom: 1rem;
        }}
        
        .toc {{
            background: var(--bg-gray);
            padding: 1.5rem;
            border-radius: 8px;
            margin-bottom: 2rem;
        }}
        
        .toc ul {{
            list-style: none;
            padding-left: 1rem;
        }}
        
        .references {{
            font-size: 0.9rem;
        }}
        
        .references p {{
            margin-bottom: 0.75rem;
            padding-left: 2rem;
            text-indent: -2rem;
        }}
        
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            .container {{
                box-shadow: none;
                padding: 0;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        {html_body}
    </div>
</body>
</html>"""
        
        return html
    
    async def generate_pdf(
        self,
        title: str,
        html_content: str
    ) -> bytes:
        """
        Generate PDF report from HTML content.
        
        Args:
            title: Report title
            html_content: HTML formatted content
            
        Returns:
            PDF file bytes
        """
        logger.info(f"Generating PDF report: {title}")
        
        try:
            from weasyprint import HTML, CSS
            
            # Generate PDF from HTML
            pdf_bytes = HTML(string=html_content).write_pdf()
            
            return pdf_bytes
            
        except ImportError:
            logger.warning("WeasyPrint not available, using fallback PDF generation")
            
            # Fallback: Use reportlab for basic PDF
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            styles = getSampleStyleSheet()
            
            # Create custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                spaceAfter=30
            )
            
            story = []
            
            # Add title
            story.append(Paragraph(title, title_style))
            story.append(Spacer(1, 12))
            
            # Add metadata
            story.append(Paragraph(
                f"Generated on {datetime.utcnow().strftime('%B %d, %Y')}",
                styles['Normal']
            ))
            story.append(Spacer(1, 24))
            
            # Add content (simplified - strip HTML)
            clean_text = re.sub(r'<[^>]+>', '', html_content)
            paragraphs = clean_text.split('\n\n')
            
            for para in paragraphs[:50]:  # Limit for basic fallback
                if para.strip():
                    story.append(Paragraph(para.strip(), styles['Normal']))
                    story.append(Spacer(1, 12))
            
            doc.build(story)
            
            return buffer.getvalue()
    
    async def format_citations(
        self,
        sources: List[Dict[str, Any]],
        style: str = "APA"
    ) -> str:
        """
        Format citations in specified style.
        
        Args:
            sources: List of sources
            style: Citation style (APA, MLA, Chicago)
            
        Returns:
            Formatted citation string
        """
        citations = []
        
        for i, source in enumerate(sources, 1):
            title = source.get("title", "Untitled")
            url = source.get("url", "")
            author = source.get("author") or source.get("authors", ["Unknown"])
            if isinstance(author, list):
                author = ", ".join(author[:3])
                if len(source.get("authors", [])) > 3:
                    author += " et al."
            
            published = source.get("published_at", "")
            if published:
                try:
                    if isinstance(published, str):
                        # Try to parse date
                        date_obj = datetime.fromisoformat(published.replace('Z', '+00:00'))
                        year = date_obj.year
                    else:
                        year = published
                except:
                    year = published[:4] if len(str(published)) >= 4 else "n.d."
            else:
                year = "n.d."
            
            retrieved_date = datetime.utcnow().strftime("%B %d, %Y")
            
            if style.upper() == "APA":
                # APA 7th Edition format
                citation = f"[{i}] {author} ({year}). *{title}*. Retrieved {retrieved_date}, from {url}"
            
            elif style.upper() == "MLA":
                # MLA 9th Edition format
                citation = f"[{i}] {author}. \"{title}.\" *Web*, {year}, {url}. Accessed {retrieved_date}."
            
            elif style.upper() == "CHICAGO":
                # Chicago 17th Edition format
                citation = f"[{i}] {author}. \"{title}.\" Accessed {retrieved_date}. {url}."
            
            else:
                # Default simple format
                citation = f"[{i}] {author}. {title}. {url}"
            
            citations.append(citation)
        
        return "\n\n".join(citations)
    
    async def create_summary(
        self,
        content: str,
        max_length: int = 500
    ) -> str:
        """
        Create an executive summary from report content.
        
        Args:
            content: Full report content
            max_length: Maximum summary length in characters
            
        Returns:
            Executive summary string
        """
        prompt = f"""Create a concise executive summary of the following research report.

The summary should:
1. Be {max_length} characters or less
2. Start with the main conclusion or most important finding
3. Highlight 2-3 key findings with specific data points or statistics
4. Mention the scope of research (number of sources, types of sources)
5. Be written in clear, professional language
6. NEVER use placeholder text like [topic] or [finding]
7. Include the confidence level of the findings

REPORT CONTENT:
{content[:5000]}

Write the executive summary:"""
        
        try:
            # Guard: if the report content is essentially empty, produce a
            # graceful summary rather than sending blank text to the LLM.
            stripped_content = content.strip() if content else ""
            if len(stripped_content) < 80:
                logger.warning(
                    "[SUMMARY] Report content is too short for executive summary — "
                    "returning graceful fallback"
                )
                return (
                    "This research collected and analyzed multiple sources on the "
                    "requested topic. While relevant sources were identified, the "
                    "automated extraction pipeline was unable to distill specific "
                    "findings with high confidence. The report sections below present "
                    "the available evidence. Further manual review of the cited sources "
                    "is recommended to extract additional insights."
                )

            summary = await self.llm.generate(
                prompt=prompt,
                model=settings.report_generator_model,
                temperature=0.4,
                max_tokens=800
            )
            
            # Ensure it's within length
            if len(summary) > max_length:
                summary = summary[:max_length-3] + "..."
            
            return summary.strip()
            
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return (
                "This research identified relevant sources on the topic but the "
                "executive summary could not be automatically generated. Please "
                "review the report sections below for the available evidence and analysis."
            )
    
    async def structure_findings(
        self,
        findings: List[Dict[str, Any]],
        query: str
    ) -> List[Dict[str, Any]]:
        """
        Structure findings into logical report sections.
        
        Args:
            findings: List of research findings
            query: Original research query
            
        Returns:
            List of structured sections
        """
        if not findings:
            return [{
                "title": "Research Summary",
                "content": "The research process analyzed available sources but found limited directly applicable findings. This section summarizes what information was gathered and identifies areas that require further investigation.",
                "order": 1
            }]
        
        # Group findings by type or theme
        findings_text = "\n".join([
            f"[{i}] {f.get('title', 'Finding')}: {f.get('content', '')[:400]}"
            for i, f in enumerate(findings)
        ])
        
        prompt = f"""Organize these research findings into logical report sections.

RESEARCH QUERY: {query}

FINDINGS:
{findings_text}

Create 3-6 thematic sections that logically organize these findings.
Each section should:
- Have a clear, descriptive title (NOT generic like "Key Findings" — make it specific to the topic)
- Combine related findings into a coherent narrative
- Never use placeholder text

Respond in JSON format:
{{
    "sections": [
        {{
            "title": "Specific Descriptive Section Title",
            "summary": "Brief summary of what this section covers",
            "finding_indices": [0, 1, 2],
            "order": 1
        }}
    ]
}}"""
        
        try:
            result = await self.llm.generate(
                prompt=prompt,
                model=settings.report_generator_model,
                temperature=0.5,
                max_tokens=1000
            )
            
            import json
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                structure = json.loads(json_match.group())
                
                sections = []
                for sec in structure.get("sections", []):
                    # Combine content from relevant findings
                    indices = sec.get("finding_indices", [])
                    content_parts = [sec.get("summary", "")]
                    
                    for idx in indices:
                        if 0 <= idx < len(findings):
                            finding = findings[idx]
                            content_parts.append(f"\n\n**{finding.get('title', '')}**")
                            content_parts.append(finding.get('content', ''))
                    
                    sections.append({
                        "title": sec.get("title", f"Section {sec.get('order', 1)}"),
                        "content": "\n".join(content_parts),
                        "order": sec.get("order", len(sections) + 1)
                    })
                
                return sorted(sections, key=lambda x: x.get("order", 0))
                
        except Exception as e:
            logger.error(f"Section structuring failed: {e}")
        
        # Fallback: create structured sections from findings
        return [{
            "title": f"Research Findings: {query[:50]}",
            "content": "\n\n".join([
                f"**{f.get('title', 'Finding')}**\n{f.get('content', '')}"
                for f in findings
            ]),
            "order": 1
        }]


# Singleton instance
formatting_tools = FormattingTools()
