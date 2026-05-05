"""
Fact-Checker Agent
Responsible for validating and verifying information accuracy.

Phase 1: reads sources and organized findings from MongoDB by session_id
instead of receiving them in the context dict.
"""

from typing import Dict, Any, List
from datetime import datetime

from app.agents.base_agent import BaseAgent, AgentStatus
from app.tools.validation_tools import ValidationTools
from app.config import settings
from app.utils.logging import logger
from app.database.repositories import SourceRepository, FindingRepository, ResearchRepository


class FactCheckerAgent(BaseAgent):
    """
    Fact-Checker Agent - Validation and verification specialist.
    
    Responsibilities:
    - Cross-reference claims across sources
    - Verify statistics and numerical claims
    - Check source credibility and authority
    - Detect potential bias in sources
    - Score confidence levels for findings
    """
    
    def __init__(self):
        system_prompt = """You are a rigorous fact-checker who verifies all claims with precision.

Your responsibilities:
1. Cross-reference claims against multiple independent sources
2. Verify statistics and numerical data for accuracy
3. Assess source credibility and authority
4. Detect potential bias or misleading information
5. Assign confidence scores based on verification results

Guidelines:
- Apply skeptical scrutiny to all claims
- Require multiple independent sources for verification
- Note when claims cannot be fully verified
- Flag potentially misleading or out-of-context information
- Be especially careful with statistics and numerical claims
- Consider source expertise and potential conflicts of interest
- Mark uncertainty clearly - it's better to say "unverified" than to guess

Your verification must be thorough and honest."""
        
        super().__init__(
            name="Fact-Checker",
            role="Validation and verification specialist",
            system_prompt=system_prompt,
            model=settings.fact_checker_model,
            temperature=0.2,  # Low temperature for consistency
            max_tokens=3000,
            timeout=settings.agent_timeout
        )
        
        self.validation_tools = ValidationTools()
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute fact-checking on analyzed findings.
        
        Phase 1: Loads sources from MongoDB and organized findings from
        pipeline_data by session_id.
        """
        query = context.get("query", "")
        session_id = context.get("session_id", "")

        # ── Phase 1: query MongoDB ────────────────────────────────
        sources: List[Dict[str, Any]] = []
        findings: List[Dict[str, Any]] = []
        insights: List[str] = []

        if session_id:
            # Sources from Source collection
            source_docs = await SourceRepository.get_by_research(session_id)
            sources = [self._source_doc_to_dict(s) for s in source_docs]

            # Organized findings from pipeline_data
            findings = await ResearchRepository.get_pipeline_data(session_id, "organized_findings") or []
            insights = await ResearchRepository.get_pipeline_data(session_id, "key_insights") or []

            # Fallback: load raw findings from FindingRepository if pipeline_data is empty
            if not findings:
                logger.warning(
                    f"[FACT_CHECKER] organized_findings empty in pipeline_data for session {session_id}, "
                    f"loading raw findings from FindingRepository"
                )
                finding_docs = await FindingRepository.get_by_research(session_id)
                findings = [self._finding_doc_to_dict(f) for f in finding_docs]
        else:
            # Backward compat / tests
            sources = context.get("sources", [])
            findings = context.get("organized_findings", [])
            insights = context.get("key_insights", [])

        # Fallback chain (context may carry raw_findings from orchestrator)
        if not findings:
            findings = context.get("consolidated_findings", [])
        if not findings:
            findings = context.get("raw_findings", [])
        # ──────────────────────────────────────────────────────────

        logger.info(
            f"Fact-Checker loaded state: session={session_id}, "
            f"sources={len(sources)}, findings={len(findings)}, insights={len(insights)}"
        )
        
        logger.info(f"Fact-Checker starting verification for: {query} ({len(findings)} findings, {len(sources)} sources)")
        
        try:
            await self._set_status(AgentStatus.IN_PROGRESS)
            await self._update_progress(5, "Beginning fact-checking process...")
            
            # Step 1: Check source credibility
            await self._update_progress(10, "Assessing source credibility...")
            source_credibility = await self._check_sources_credibility(sources[:30])
            
            # Step 2: Validate findings
            await self._update_progress(30, "Validating findings against sources...")
            validated_findings = await self._validate_findings(findings, sources)
            
            # Step 3: Verify statistics
            await self._update_progress(55, "Verifying statistics and claims...")
            stats_verification = await self._verify_statistics(findings, sources)
            
            # Step 4: Detect bias
            await self._update_progress(70, "Detecting potential bias...")
            bias_analysis = await self._analyze_bias(sources[:20])
            
            # Step 5: Calculate overall confidence
            await self._update_progress(85, "Calculating confidence scores...")
            confidence_summary = self._calculate_confidence(
                validated_findings, source_credibility, stats_verification
            )
            
            # Step 6: Generate verification summary
            await self._update_progress(95, "Generating verification summary...")
            verification_summary = await self._generate_summary(
                query, validated_findings, confidence_summary
            )
            
            await self._update_progress(100, f"Fact-checking complete: {len(validated_findings)} findings verified")
            await self._set_status(AgentStatus.COMPLETED)
            
            return {
                "status": "completed",
                "query": query,
                "validated_findings": validated_findings,
                "source_credibility": source_credibility,
                "statistics_verification": stats_verification,
                "bias_analysis": bias_analysis,
                "confidence_summary": confidence_summary,
                "verification_summary": verification_summary,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Fact-Checker execution failed: {e}")
            await self._set_status(AgentStatus.FAILED, str(e))
            return {
                "status": "failed",
                "error": str(e),
                "validated_findings": findings,  # Return unvalidated
                "confidence_summary": {"overall": 0.5, "note": "Verification failed"}
            }
    
    async def _check_sources_credibility(
        self,
        sources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Check credibility of all sources."""
        
        credibility_results = []
        
        for i, source in enumerate(sources):
            url = source.get("url", "")
            if url:
                try:
                    result = await self.validation_tools.check_source_credibility(url)
                    credibility_results.append({
                        "source_index": i,
                        "url": url,
                        "title": source.get("title", ""),
                        **result
                    })
                except Exception as e:
                    logger.warning(f"Credibility check failed for {url}: {e}")
                    credibility_results.append({
                        "source_index": i,
                        "url": url,
                        "title": source.get("title", ""),
                        "credibility_score": 0.5,
                        "warnings": ["Could not verify credibility"],
                        "error": str(e)
                    })
            
            # Progress update every 10 sources
            if (i + 1) % 10 == 0:
                progress = 10 + int((i / len(sources)) * 20)
                await self._update_progress(progress, f"Checked {i+1}/{len(sources)} sources...")
        
        return credibility_results
    
    async def _validate_findings(
        self,
        findings: List[Dict[str, Any]],
        sources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Validate findings through cross-referencing."""
        
        validated = []
        
        for i, finding in enumerate(findings):
            content = finding.get("content", "") or finding.get("title", "")
            
            if content:
                try:
                    verification = await self.validation_tools.cross_reference_claim(
                        claim=content,
                        sources=sources[:25]  # Cross-reference against more sources for better verification
                    )
                    
                    validated.append({
                        **finding,
                        "verified": verification.get("verified", False),
                        "verification_verdict": verification.get("verdict", "unverified"),
                        "confidence_score": verification.get("confidence", 0.5),
                        "supporting_sources": verification.get("supporting_sources", []),
                        "contradicting_sources": verification.get("contradicting_sources", []),
                        "verification_summary": verification.get("summary", "")
                    })
                except Exception as e:
                    logger.warning(f"Finding validation failed: {e}")
                    validated.append({
                        **finding,
                        "verified": False,
                        "verification_verdict": "error",
                        "confidence_score": 0.5,
                        "verification_error": str(e)
                    })
            else:
                validated.append({**finding, "verified": False, "confidence_score": 0.3})
            
            # Progress update
            progress = 30 + int((i / len(findings)) * 25)
            await self._update_progress(progress, f"Validated {i+1}/{len(findings)} findings...")
        
        return validated
    
    async def _verify_statistics(
        self,
        findings: List[Dict[str, Any]],
        sources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Verify statistical claims in findings."""
        
        stats_results = []
        
        # Look for findings with statistics
        for finding in findings:
            content = finding.get("content", "")
            finding_type = finding.get("finding_type", "")
            
            # Check if this finding contains statistics
            import re
            has_numbers = bool(re.search(r'\d+(?:\.\d+)?%?', content))
            is_statistic = finding_type == "statistic"
            
            if has_numbers or is_statistic:
                try:
                    verification = await self.validation_tools.verify_statistics(
                        statistic=content,
                        sources=sources[:10]
                    )
                    stats_results.append({
                        "finding_title": finding.get("title", ""),
                        "original_claim": content[:200],
                        **verification
                    })
                except Exception as e:
                    logger.warning(f"Statistics verification failed: {e}")
        
        return stats_results
    
    async def _analyze_bias(
        self,
        sources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze potential bias across sources."""
        
        bias_scores = []
        bias_types = []
        
        # Sample sources for bias analysis
        for source in sources[:10]:
            content = source.get("snippet", "") or source.get("content", "")
            if content:
                try:
                    result = await self.validation_tools.detect_bias(content)
                    bias_scores.append(result.get("bias_score", 0.5))
                    if result.get("bias_types"):
                        bias_types.extend(result.get("bias_types", []))
                except Exception as e:
                    logger.warning(f"Bias detection failed: {e}")
        
        avg_bias = sum(bias_scores) / len(bias_scores) if bias_scores else 0.5
        
        return {
            "average_bias_score": avg_bias,
            "bias_level": "low" if avg_bias < 0.3 else "moderate" if avg_bias < 0.6 else "high",
            "common_bias_types": list(set(bias_types)),
            "sources_analyzed": len(bias_scores),
            "recommendation": self._get_bias_recommendation(avg_bias)
        }
    
    def _get_bias_recommendation(self, bias_score: float) -> str:
        """Get recommendation based on bias score."""
        if bias_score < 0.3:
            return "Sources appear relatively balanced and objective."
        elif bias_score < 0.6:
            return "Some bias detected. Consider seeking additional perspectives."
        else:
            return "Significant bias detected. Findings should be interpreted with caution."

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
            "type": doc.finding_type.value if hasattr(doc.finding_type, "value") else str(doc.finding_type or "insight"),
            "source_refs": meta.get("source_refs", ""),
            "resolved_sources": meta.get("resolved_sources", []),
            "preliminary_credibility": meta.get("preliminary_credibility", "medium"),
            "confidence_score": doc.confidence_score,
            "verified": doc.verified,
        }
    
    def _calculate_confidence(
        self,
        validated_findings: List[Dict[str, Any]],
        source_credibility: List[Dict[str, Any]],
        stats_verification: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate overall confidence scores."""
        
        # Finding confidence
        finding_scores = [f.get("confidence_score", 0.5) for f in validated_findings]
        avg_finding_confidence = sum(finding_scores) / len(finding_scores) if finding_scores else 0.5
        
        # Source credibility
        cred_scores = [s.get("credibility_score", 0.5) for s in source_credibility]
        avg_source_credibility = sum(cred_scores) / len(cred_scores) if cred_scores else 0.5
        
        # Statistics verification
        stats_verified = [s for s in stats_verification if s.get("verified", False)]
        stats_accuracy = len(stats_verified) / len(stats_verification) if stats_verification else 1.0
        
        # Overall confidence (weighted average)
        overall = (
            avg_finding_confidence * 0.4 +
            avg_source_credibility * 0.35 +
            stats_accuracy * 0.25
        )
        
        return {
            "overall_confidence": round(overall, 2),
            "finding_confidence": round(avg_finding_confidence, 2),
            "source_credibility": round(avg_source_credibility, 2),
            "statistics_accuracy": round(stats_accuracy, 2),
            "verified_findings": len([f for f in validated_findings if f.get("verified")]),
            "total_findings": len(validated_findings),
            "confidence_level": "high" if overall > 0.75 else "medium" if overall > 0.5 else "low"
        }
    
    async def _generate_summary(
        self,
        query: str,
        validated_findings: List[Dict[str, Any]],
        confidence_summary: Dict[str, Any]
    ) -> str:
        """Generate a summary of the fact-checking process."""
        
        verified_count = confidence_summary.get("verified_findings", 0)
        total_count = confidence_summary.get("total_findings", 0)
        confidence_level = confidence_summary.get("confidence_level", "medium")
        
        summary = f"""Fact-Check Summary for: "{query}"

Verification Results:
- {verified_count} of {total_count} findings verified
- Overall confidence level: {confidence_level.upper()}
- Source credibility score: {confidence_summary.get('source_credibility', 0.5):.0%}

"""
        
        if confidence_level == "high":
            summary += "The research findings are well-supported by credible sources with minimal contradictions."
        elif confidence_level == "medium":
            summary += "The research findings have moderate support. Some claims could benefit from additional verification."
        else:
            summary += "The research findings have limited verification. Interpret results with caution and seek additional sources."
        
        return summary
