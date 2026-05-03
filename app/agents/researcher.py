"""
Researcher Agent
Responsible for searching and gathering information from multiple sources.
"""

from typing import Dict, Any, List
from datetime import datetime

from app.agents.base_agent import BaseAgent, AgentStatus
from app.tools.search_tools import SearchTools
from app.config import settings
from app.utils.logging import logger


class ResearcherAgent(BaseAgent):
    """
    Researcher Agent - Search and information gathering specialist.
    
    Responsibilities:
    - Search multiple sources (Google, NewsAPI, ArXiv, PubMed, Wikipedia)
    - Collect raw information
    - Filter for relevance to the query
    - Track sources and metadata
    - Parallel search execution
    """
    
    def __init__(self):
        system_prompt = """You are a research expert who searches multiple sources to gather comprehensive, RELEVANT information.

Your responsibilities:
1. Analyze the research query to identify key search terms and concepts
2. Search across multiple sources (web, news, academic, encyclopedic)
3. CRITICALLY evaluate each source for relevance to the specific query
4. Discard sources that are not directly related to the research topic
5. Extract concrete data points, statistics, and findings from relevant sources
6. Track source metadata for attribution

Guidelines:
- QUALITY over quantity — 20 highly relevant sources beat 200 irrelevant ones
- Only include sources that directly address the research query
- Prioritize sources with specific data, statistics, or expert analysis
- Prioritize authoritative and credible sources (academic, government, established media)
- Note publication dates for recency
- Preserve original source attribution
- NEVER include sources just to increase count — every source must add value

Output structured findings with clear source attribution and concrete data points."""
        
        super().__init__(
            name="Researcher",
            role="Search and information gathering specialist",
            system_prompt=system_prompt,
            model=settings.researcher_model,
            temperature=0.3,
            max_tokens=4096,
            timeout=settings.agent_timeout
        )
        
        self.search_tools = SearchTools()
        self.sources_found: Dict[str, int] = {}
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute research across all sources.
        
        Args:
            context: Contains 'query', 'focus_areas', 'source_preferences', 'max_sources'
            
        Returns:
            Dictionary with sources and raw findings
        """
        query = context.get("query", "")
        focus_areas = context.get("focus_areas", [])
        source_preferences = context.get("source_preferences", [])
        max_sources = context.get("max_sources", 300)
        research_mode = context.get("research_mode", "auto")
        search_hints = context.get("search_hints", "")
        # Store as instance flag so inner methods can reference it
        self._is_deep = research_mode == "deep"

        logger.info(f"Researcher starting search for: {query} (mode={research_mode}, deep={self._is_deep})")
        if search_hints:
            logger.info(f"Researcher search_hints from UserProxy: {search_hints[:120]}")
        
        try:
            await self._set_status(AgentStatus.IN_PROGRESS)
            await self._update_progress(5, "Analyzing query and preparing search strategy...")
            
            # Generate search queries based on focus areas
            search_queries = await self._generate_search_queries(query, focus_areas)

            # If UserProxy provided search hints, add as extra query
            if search_hints and search_hints != query:
                search_queries.append(search_hints)
            
            await self._update_progress(10, f"Generated {len(search_queries)} search queries")
            
            # Execute parallel searches
            all_sources = []
            sources_by_api = {
                "google": [],
                "newsapi": [],
                "arxiv": [],
                "pubmed": [],
                "wikipedia": []
            }
            
            # Deep mode fetches significantly more per API call
            base_per_source = max(5, min(15, max_sources // (len(search_queries) * 3)))
            results_per_source = min(base_per_source * 2, 25) if self._is_deep else base_per_source
            
            for i, search_query in enumerate(search_queries):
                progress = 10 + int((i / len(search_queries)) * 40)
                await self._update_progress(
                    progress,
                    f"Searching: {search_query[:50]}..."
                )

                # Micro-update callback: fires as each API finishes
                async def _on_api_done(api_name, count, done, total):
                    await self._update_progress(
                        progress + int((done / total) * (40 // len(search_queries))),
                        f"Fetched {count} results from {api_name} ({done}/{total} APIs done)"
                    )

                # Execute parallel search across all APIs
                results = await self.search_tools.search_all(
                    query=search_query,
                    max_results_per_source=results_per_source,
                    on_api_complete=_on_api_done
                )
                
                # Aggregate results
                for api, items in results.items():
                    sources_by_api[api].extend(items)
                    all_sources.extend(items)
                
                # Don't over-collect — we'll filter for quality
                if len(all_sources) >= max_sources * 2:
                    break
            
            await self._update_progress(55, f"Collected {len(all_sources)} sources, deduplicating...")
            
            # Deduplicate sources by URL
            seen_urls = set()
            unique_sources = []
            for source in all_sources:
                url = source.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_sources.append(source)
            
            await self._update_progress(60, f"Filtering {len(unique_sources)} sources for relevance...")
            
            # CRITICAL: Filter sources for relevance to the query
            relevant_sources = await self._filter_relevant_sources(query, unique_sources)
            
            # Limit to max_sources
            relevant_sources = relevant_sources[:max_sources]
            
            await self._update_progress(80, f"{len(relevant_sources)} relevant sources found (filtered from {len(unique_sources)})...")
            
            # Count sources by API
            self.sources_found = {
                api: len([s for s in relevant_sources if s.get("api_source") == api])
                for api in sources_by_api.keys()
            }
            self.sources_found["total"] = len(relevant_sources)
            self.sources_found["total_before_filtering"] = len(unique_sources)
            
            # Extract key information using LLM — pass all relevant sources
            await self._update_progress(85, "Extracting key information from relevant sources...")
            
            raw_findings = await self._extract_key_info(query, relevant_sources[:40])
            
            await self._update_progress(100, f"Research complete: {len(relevant_sources)} relevant sources, {len(raw_findings)} findings extracted")
            await self._set_status(AgentStatus.COMPLETED)
            
            return {
                "status": "completed",
                "query": query,
                "sources": relevant_sources,
                "sources_count": self.sources_found,
                "raw_findings": raw_findings,
                "search_queries_used": search_queries,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Researcher execution failed: {e}")
            await self._set_status(AgentStatus.FAILED, str(e))
            return {
                "status": "failed",
                "error": str(e),
                "sources": [],
                "sources_count": {"total": 0}
            }
    
    async def _generate_search_queries(
        self,
        query: str,
        focus_areas: List[str]
    ) -> List[str]:
        """Generate optimized search queries based on the main query and focus areas."""
        
        queries = [query]  # Always include original query
        
        # Add focus area variations
        for area in focus_areas:
            queries.append(f"{query} {area}")
        
        # Use LLM to generate additional relevant queries
        prompt = f"""Generate 3-5 highly specific search queries to research this topic THOROUGHLY.

Main Query: {query}
Focus Areas: {', '.join(focus_areas) if focus_areas else 'General'}

Rules:
- Each query must be DIRECTLY relevant to the main topic
- Include queries that would find statistics, data, and expert analysis
- Include queries that would find recent studies and reports
- Make queries specific enough to avoid irrelevant results
- Produce SHORT KEYWORD-STYLE queries (3-8 words), NOT full questions or sentences
  Example: "AI job market impact 2026 statistics" instead of "What is the impact of AI on the job market?"
- DO NOT generate generic or tangential queries

Return only the queries, one per line, no numbering or explanation."""
        
        try:
            response = await self.think(prompt)
            additional_queries = [q.strip() for q in response.strip().split('\n') if q.strip() and len(q.strip()) > 5]
            queries.extend(additional_queries[:5])
        except Exception as e:
            logger.warning(f"Query generation failed: {e}")
        
        # Deep mode uses more queries for broader coverage
        return queries[:12] if getattr(self, '_is_deep', False) else queries[:8]
    
    async def _filter_relevant_sources(
        self,
        query: str,
        sources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter sources for relevance to the research query using keyword matching + LLM."""
        
        if not sources:
            return []
        
        # Step 1: Quick keyword-based pre-filtering
        query_lower = query.lower()
        query_words = set(query_lower.split())
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'of', 'in', 'on', 'at', 'to', 'for', 'and', 'or', 'but', 'not', 'with', 'how', 'what', 'why', 'when', 'where', 'which', 'who', 'does', 'do', 'can', 'could', 'would', 'should', 'its', 'it', 'this', 'that', 'these', 'those', 'has', 'have', 'had', 'will', 'be', 'been', 'being', 'from', 'by', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between', 'under', 'over', 'then', 'than', 'so', 'if'}
        query_keywords = query_words - stop_words
        
        scored_sources = []
        for source in sources:
            title = (source.get("title", "") or "").lower()
            snippet = (source.get("snippet", "") or "").lower()
            combined = f"{title} {snippet}"
            
            # Count keyword matches
            keyword_hits = sum(1 for kw in query_keywords if kw in combined)
            keyword_ratio = keyword_hits / max(len(query_keywords), 1)
            
            # Boost academic sources
            source_type = source.get("source_type", "")
            type_boost = 1.2 if source_type == "academic" else 1.0
            
            relevance_score = keyword_ratio * type_boost
            source["_relevance_score"] = relevance_score
            scored_sources.append(source)
        
        # Sort by relevance score descending
        scored_sources.sort(key=lambda s: s.get("_relevance_score", 0), reverse=True)
        
        # Take top candidates (generous to allow LLM to refine)
        candidates = scored_sources[:min(150, len(scored_sources))]
        
        # Step 2: LLM-based relevance filtering on top candidates
        # Process in batches of 20
        relevant_sources = []
        batch_size = 20
        
        for batch_start in range(0, len(candidates), batch_size):
            batch = candidates[batch_start:batch_start + batch_size]
            
            source_list = []
            for i, source in enumerate(batch):
                title = source.get("title", "Untitled")
                snippet = (source.get("snippet", "") or "")[:200]
                source_list.append(f"[{i}] {title} — {snippet}")
            
            prompt = f"""You are a research relevance filter. Evaluate which sources are relevant to this research query.

RESEARCH QUERY: {query}

SOURCES:
{chr(10).join(source_list)}

For each source, respond with ONLY the index numbers of sources that are relevant.
A source is relevant if it touches on the research topic, provides useful background or context, contains data or expert perspectives, or could inform any aspect of the query.
Be INCLUSIVE — when in doubt, KEEP the source. Only reject sources about a genuinely unrelated topic with no meaningful connection to the query.

Respond with ONLY a comma-separated list of relevant source indices (e.g., "0, 2, 5, 7").
If none are relevant, respond with "NONE"."""
            
            try:
                await self._update_progress(
                    62 + int((batch_start / len(candidates)) * 15),
                    f"Evaluating sources {batch_start + 1}–{batch_start + len(batch)} of {len(candidates)} for relevance…"
                )
                response = await self.think(prompt)
                response = response.strip()
                
                if response.upper() != "NONE":
                    # Parse indices
                    import re
                    selected_indices = set()
                    indices = re.findall(r'\d+', response)
                    for idx_str in indices:
                        idx = int(idx_str)
                        if 0 <= idx < len(batch):
                            relevant_sources.append(batch[idx])
                            selected_indices.add(idx)

                    # Log rejected sources for auditing
                    for idx, source in enumerate(batch):
                        if idx not in selected_indices:
                            title = (source.get("title", "") or "")[:60]
                            score = source.get("_relevance_score", 0)
                            logger.info(f"[FILTER_REJECTED] '{title}' (kw_score={score:.2f}) — LLM did not select")
                else:
                    # LLM said NONE — log all as rejected
                    for idx, source in enumerate(batch):
                        title = (source.get("title", "") or "")[:60]
                        score = source.get("_relevance_score", 0)
                        logger.info(f"[FILTER_REJECTED] '{title}' (kw_score={score:.2f}) — LLM returned NONE")
            except Exception as e:
                logger.warning(f"LLM relevance filtering failed for batch: {e}")
                # Fallback: include sources with decent keyword score
                for source in batch:
                    if source.get("_relevance_score", 0) >= 0.1:
                        relevant_sources.append(source)
        
        # Clean up temporary score field
        for source in relevant_sources:
            source.pop("_relevance_score", None)
        
        # Ensure we have at least some sources (fallback to keyword-filtered)
        if len(relevant_sources) < 10:
            logger.warning(f"LLM filtering returned only {len(relevant_sources)} sources, using keyword fallback")
            for source in scored_sources[:50]:
                source.pop("_relevance_score", None)
                if source not in relevant_sources:
                    relevant_sources.append(source)
                if len(relevant_sources) >= 50:
                    break
        
        logger.info(f"Relevance filtering: {len(sources)} → {len(relevant_sources)} relevant sources")
        return relevant_sources
    
    async def _extract_key_info(
        self,
        query: str,
        sources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract key information and findings from sources."""
        
        if not sources:
            return []
        
        # Process in batches to cover more sources (deep mode covers 60 vs 45)
        all_findings = []
        batch_size = 15
        max_to_process = 60 if getattr(self, '_is_deep', False) else 45

        for batch_start in range(0, min(len(sources), max_to_process), batch_size):
            batch = sources[batch_start:batch_start + batch_size]
            await self._update_progress(
                85 + int((batch_start / min(len(sources), max_to_process)) * 12),
                f"Extracting findings from sources {batch_start + 1}–{batch_start + len(batch)} of {min(len(sources), max_to_process)}…"
            )
            batch_findings = await self._extract_from_batch(query, batch, batch_start)
            all_findings.extend(batch_findings)
        
        # Deduplicate similar findings
        if len(all_findings) > 10:
            all_findings = await self._deduplicate_findings(query, all_findings)

        # Hard emergency fallback: if LLM extraction produced 0 findings
        # but we have sources, create minimal findings from source data
        # so the pipeline never runs with an empty findings list.
        if len(all_findings) == 0 and sources:
            logger.warning(
                f"[EXTRACT] LLM extraction returned 0 findings across all batches. "
                f"Creating emergency findings from {len(sources)} source titles/snippets."
            )
            all_findings = self._create_emergency_findings_from_sources(query, sources)

        return all_findings
    
    async def _extract_from_batch(
        self,
        query: str,
        sources: List[Dict[str, Any]],
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Extract findings from a batch of sources."""
        import json as _json
        import re as _re

        if not sources:
            return []

        # ── Validate source content & build summaries ─────────────
        source_summaries = []
        source_url_index: Dict[int, Dict[str, str]] = {}
        empty_content_count = 0

        for i, source in enumerate(sources):
            title = source.get("title", "Untitled")
            raw_text = (source.get("snippet") or source.get("description") or "").strip()
            debug_line = f"DEBUG: Extracting from {title[:80]} - Content Length: {len(raw_text)}"
            print(debug_line)
            logger.info(debug_line)
            if i == 0:
                logger.info(f"[EXTRACT_PAYLOAD] First source text length: {len(raw_text)}")
            if len(raw_text) < 100:
                warning_msg = (
                    f"[EXTRACT_PAYLOAD] Source content is suspiciously empty! "
                    f"source_index={offset + i + 1} length={len(raw_text)}"
                )
                print(warning_msg)
                logger.warning(warning_msg)

            snippet = raw_text
            url = source.get("url", "")
            author = source.get("author", "") or ", ".join(source.get("authors", [])[:2])
            year = source.get("published_at", "")
            if year and len(str(year)) > 4:
                year = str(year)[:4]
            api_src = source.get("api_source", "")

            # Warn on empty content
            if not snippet:
                empty_content_count += 1
                logger.warning(
                    f"[EXTRACT] Source [{offset + i + 1}] '{title[:60]}' "
                    f"(api={api_src}) has EMPTY snippet/content — LLM will only see the title"
                )
                # Use title as minimal content so the LLM has *something*
                snippet = f"(No abstract/snippet available — title only: {title})"

            source_summaries.append(
                f"[{offset + i + 1}] ({year}) {title} by {author} | {url}\n{snippet[:600]}"
            )
            source_url_index[offset + i + 1] = {
                "title": title, "url": url, "api_source": api_src
            }

        if empty_content_count > 0:
            logger.warning(
                f"[EXTRACT] {empty_content_count}/{len(sources)} sources in this batch have empty content"
            )

        context = "\n\n".join(source_summaries)

        # ── Prompt: require STRICT JSON array output ──────────────
        example_json = _json.dumps([
            {
                "finding": "Global AI spending reached $150 billion in 2025, up 35% year-over-year.",
                "sources": [1, 4],
                "credibility": "high"
            },
            {
                "finding": "A 2025 Stanford study found 42% of enterprises adopted generative AI.",
                "sources": [2],
                "credibility": "medium"
            }
        ])

        prompt = f"""You are a research data-extraction engine. Read the sources below and extract concrete, specific findings relevant to the research query.

RESEARCH QUERY: {query}

SOURCES:
{context}

INSTRUCTIONS:
- Extract at least 1-3 key factual findings that DIRECTLY answer or inform the research query.
- Each finding MUST contain specific data, statistics, expert opinions, or concrete insights drawn from the sources.
- DO NOT output generic or vague statements. Every finding must reference specific information visible in the sources above.
- DO NOT say "no findings" — always extract whatever relevant information exists, even if partial.
- If a source only has a title, infer the most likely factual claim it supports.

You are a data extraction sub-module.
You MUST respond ONLY with a valid, flat JSON array of objects. DO NOT include preamble, markdown formatting, or explanations.
Each element must be an object with exactly these keys:
  "finding"  — a specific, data-rich statement
  "sources"  — an array of the numeric source IDs that support it, e.g. [{offset + 1}, {offset + 3}]
  "credibility" — one of "high", "medium", or "low"
If no findings are available, return exactly: []

Example (do NOT copy these values):
{example_json}

Respond with ONLY the JSON array:"""

        try:
            response = await self.think(prompt)

            # ── Debug log: show exactly what the LLM returned ─────
            logger.info(
                f"[EXTRACT_RAW] LLM response (first 500 chars): "
                f"{response[:500]!r}"
            )

            # ── Parse JSON — aggressive cleaning before parsing ─────
            cleaned = self.clean_json_string(response)

            # Try JSON parse
            parsed = None
            try:
                parsed = _json.loads(cleaned)
            except _json.JSONDecodeError:
                parsed = None

            if parsed is None:
                logger.error(
                    f"[EXTRACT] JSON parse FAILED for batch at offset {offset}. "
                    f"Raw response (first 1200 chars): {response[:1200]!r}"
                )
                try:
                    import sentry_sdk
                    sentry_sdk.capture_message(
                        f"[EXTRACT_JSON_PARSE_FAILED] offset={offset} raw={response[:2000]}",
                        level="error"
                    )
                except Exception:
                    pass
                # ── Fallback: try the old FINDING:/SOURCES:/CREDIBILITY: format ──
                return self._parse_finding_text_format(response, source_url_index)

            if isinstance(parsed, dict):
                if isinstance(parsed.get("findings"), list):
                    parsed = parsed.get("findings", [])
                elif isinstance(parsed.get("data"), list):
                    parsed = parsed.get("data", [])
                else:
                    parsed = [parsed]

            # ── Convert JSON objects to internal finding dicts ─────
            findings: List[Dict[str, Any]] = []
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                content = (
                    str(item.get("finding") or item.get("content") or item.get("fact") or item.get("insight") or "")
                    .strip()
                )
                if not content:
                    continue
                src_ids = item.get("sources", item.get("source_ids", item.get("source_id", [])))
                if not isinstance(src_ids, list):
                    src_ids = _re.findall(r'\d+', str(src_ids))
                    src_ids = [int(x) for x in src_ids]
                cred = str(item.get("credibility", "medium")).lower()

                resolved: List[Dict[str, str]] = []
                for idx in src_ids:
                    idx = int(idx)
                    if idx in source_url_index:
                        resolved.append(source_url_index[idx])

                findings.append({
                    "content": content,
                    "type": "insight",
                    "source_refs": str(src_ids),
                    "resolved_sources": resolved,
                    "preliminary_credibility": cred,
                })

            if len(findings) == 0:
                logger.error(
                    f"[EXTRACT] JSON parsed but yielded 0 findings at offset {offset}. "
                    f"Cleaned payload (first 1200 chars): {cleaned[:1200]!r}"
                )

            logger.info(f"[EXTRACT] Parsed {len(findings)} findings from batch at offset {offset}")
            return findings

        except Exception as e:
            logger.error(f"Key info extraction failed: {e}", exc_info=True)
            return []

    @staticmethod
    def clean_json_string(raw_str: str) -> str:
        """Clean LLM output and isolate the JSON array between first '[' and last ']'."""
        import re as _re

        cleaned = (raw_str or "").strip()
        if not cleaned:
            return "[]"

        # Strip common markdown wrappers and language prefixes
        cleaned = _re.sub(r'^```(?:json|JSON)?\s*', '', cleaned)
        cleaned = _re.sub(r'\s*```\s*$', '', cleaned)
        cleaned = _re.sub(r'^(json|JSON)\s*', '', cleaned)
        cleaned = cleaned.strip()

        # Keep only the JSON array or object slice
        first_bracket = cleaned.find('[')
        first_brace = cleaned.find('{')

        start_idx = -1
        if first_bracket != -1 and first_brace != -1:
            start_idx = min(first_bracket, first_brace)
        elif first_bracket != -1:
            start_idx = first_bracket
        elif first_brace != -1:
            start_idx = first_brace

        if start_idx != -1:
            end_char = ']' if cleaned[start_idx] == '[' else '}'
            last_idx = cleaned.rfind(end_char)
            if last_idx != -1 and last_idx > start_idx:
                cleaned = cleaned[start_idx:last_idx + 1]

        return cleaned.strip()

    @staticmethod
    def _clean_extraction_json(raw_output: str) -> str:
        """Backward-compatible alias for older call sites."""
        return ResearcherAgent.clean_json_string(raw_output)

    @staticmethod
    def _parse_finding_text_format(
        response: str,
        source_url_index: Dict[int, Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """Fallback parser for the old FINDING:/SOURCES:/CREDIBILITY: text format."""
        import re as _re
        findings: List[Dict[str, Any]] = []
        current_finding: Dict[str, Any] = {}

        for line in response.split('\n'):
            line = line.strip()
            if line.upper().startswith('FINDING:'):
                if current_finding and current_finding.get("content"):
                    findings.append(current_finding)
                current_finding = {"content": line[8:].strip(), "type": "insight"}
            elif line.upper().startswith('SOURCES:'):
                raw_refs = line[8:].strip()
                current_finding["source_refs"] = raw_refs
                resolved: List[Dict[str, str]] = []
                for idx_str in _re.findall(r'\d+', raw_refs):
                    idx = int(idx_str)
                    if idx in source_url_index:
                        resolved.append(source_url_index[idx])
                current_finding["resolved_sources"] = resolved
            elif line.upper().startswith('CREDIBILITY:'):
                cred = line[12:].strip().lower()
                current_finding["preliminary_credibility"] = cred
            elif line == '---' and current_finding and current_finding.get("content"):
                findings.append(current_finding)
                current_finding = {}

        if current_finding and current_finding.get("content"):
            findings.append(current_finding)

        logger.info(f"[EXTRACT] Text-format fallback parsed {len(findings)} findings")
        return findings
    
    @staticmethod
    def _create_emergency_findings_from_sources(
        query: str,
        sources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Create minimal findings directly from source titles/snippets when LLM extraction fails."""
        findings: List[Dict[str, Any]] = []
        for i, source in enumerate(sources[:20]):
            title = (source.get("title") or "").strip()
            snippet = (source.get("snippet") or source.get("description") or "").strip()
            url = source.get("url", "")
            api_src = source.get("api_source", "")
            text = snippet if snippet else title
            if not text:
                continue
            findings.append({
                "content": text[:600],
                "type": "insight",
                "source_refs": str([i + 1]),
                "resolved_sources": [{"title": title, "url": url, "api_source": api_src}],
                "preliminary_credibility": "medium",
            })
        logger.info(f"[EXTRACT] Emergency fallback created {len(findings)} findings from source data")
        return findings

    async def _deduplicate_findings(
        self,
        query: str,
        findings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate/overlapping findings and merge their source refs."""
        
        if len(findings) <= 5:
            return findings
        
        findings_list = "\n".join([
            f"[{i}] {f.get('content', '')[:150]}"
            for i, f in enumerate(findings)
        ])
        
        prompt = f"""These are research findings for: {query}

{findings_list}

Identify which findings are saying essentially the same thing (duplicates or near-duplicates).
Return the indices of findings to KEEP (the best/most complete version of each unique finding).
Respond with ONLY a comma-separated list of indices to keep (e.g., "0, 2, 4, 7, 9")."""
        
        try:
            response = await self.think(prompt)
            import re
            indices = [int(x) for x in re.findall(r'\d+', response)]
            
            kept = []
            for idx in indices:
                if 0 <= idx < len(findings):
                    kept.append(findings[idx])
            
            if len(kept) >= 3:
                return kept
        except Exception as e:
            logger.warning(f"Deduplication failed: {e}")
        
        return findings
