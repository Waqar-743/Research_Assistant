"""
Search Tools for the Researcher Agent.
Integrates with SerpAPI, Google, NewsAPI, ArXiv, PubMed, and Wikipedia.

Phase 2: All search methods check Redis cache before making external
API calls, and store results on cache miss.
"""

import asyncio
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import feedparser
from urllib.parse import urlencode, quote_plus
import xml.etree.ElementTree as ET

import sentry_sdk

from app.config import settings
from app.utils.logging import logger
from app.services.redis_cache import get_redis


class SearchTools:
    """Collection of search tools for gathering information from multiple sources."""
    
    # Cache TTL — 24 hours for search results
    CACHE_TTL = 86400

    def __init__(self):
        self.timeout = httpx.Timeout(30.0, connect=10.0)
        self.headers = {
            "User-Agent": "ResearchAssistant/1.0 (https://github.com/multi-agent-research; research-bot)"
        }
        self._cache = get_redis()
    
    async def search_all(
        self,
        query: str,
        max_results_per_source: int = 20,
        on_api_complete: Optional[Any] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search all available sources in parallel.
        
        Args:
            query: Search query string
            max_results_per_source: Maximum results from each source
            on_api_complete: Optional async callback(api_name, count, done_count, total_apis)
            
        Returns:
            Dictionary with results from each source
        """
        logger.info(f"Starting parallel search for: {query}")
        
        api_names = ["google", "newsapi", "arxiv", "pubmed", "wikipedia"]
        completed_count = 0

        async def _run(api_name: str, coro):
            nonlocal completed_count
            try:
                result = await coro
            except Exception as exc:
                logger.error(f"[SEARCH_ALL] {api_name} raised {type(exc).__name__}: {exc}")
                result = []
            completed_count += 1
            if on_api_complete:
                await on_api_complete(api_name, len(result), completed_count, len(api_names))
            return result

        tasks = [
            _run("google", self.web_search(query, max_results_per_source)),
            _run("newsapi", self.newsapi_search(query, max_results_per_source)),
            _run("arxiv", self.arxiv_search(query, max_results_per_source)),
            _run("pubmed", self.pubmed_search(query, max_results_per_source)),
            _run("wikipedia", self.wikipedia_search(query)),
        ]

        raw_results = await asyncio.gather(*tasks)
        output = dict(zip(api_names, raw_results))

        # ── Raw payload logging + Sentry warnings ────────────────
        api_configured = {
            "google": True,  # always has DDG fallback now
            "newsapi": bool(settings.newsapi_key),
            "arxiv": True,   # no key needed
            "pubmed": True,  # no key needed
            "wikipedia": True,
        }
        total_all = 0
        for api_name in api_names:
            count = len(output[api_name])
            total_all += count
            logger.info(f"[RAW_PAYLOAD] {api_name}: {count} results for '{query[:60]}'")
            if count == 0 and api_configured.get(api_name):
                sentry_sdk.capture_message(
                    f"API {api_name} returned 0 results for: {query[:120]}",
                    level="warning",
                )
        logger.info(f"[SEARCH_TOTAL] {total_all} results across all APIs for '{query[:60]}'")
        # ─────────────────────────────────────────────────────────

        return output
    
    async def web_search(
        self,
        query: str,
        num_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search the web using SerpAPI (preferred), Google Custom Search, or DuckDuckGo (free fallback).
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            List of search results with title, url, snippet
        """
        # Try SerpAPI first (preferred)
        if settings.serpapi_key:
            results = await self.serpapi_search(query, num_results)
            if results:
                return results
            logger.warning("SerpAPI returned 0 results, falling through to next provider")
        
        # Fallback to Google Custom Search
        if settings.google_api_key and settings.google_search_engine_id:
            results = await self.google_search(query, num_results)
            if results:
                return results
            logger.warning("Google Custom Search returned 0 results, falling through")
        
        # Final fallback: DuckDuckGo (free, no key required)
        logger.info("Using DuckDuckGo fallback for web search")
        return await self.duckduckgo_search(query, num_results)
    
    async def serpapi_search(
        self,
        query: str,
        num_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search using SerpAPI (Google Search Results API).
        Phase 2: checks Redis cache first.
        """
        if not settings.serpapi_key:
            logger.warning("SerpAPI key not configured")
            return []

        # ── Redis cache check ────────────────────────────────────
        cache_query = f"serpapi:{query}:{num_results}"
        cached = await self._cache.get_search_cache("serpapi", cache_query)
        if cached is not None:
            return cached
        # ─────────────────────────────────────────────────────────
        
        results = []
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                params = {
                    "api_key": settings.serpapi_key,
                    "engine": "google",
                    "q": query,
                    "num": min(num_results, 100),
                    "hl": "en",
                    "gl": "us"
                }
                
                response = await client.get(
                    "https://serpapi.com/search",
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Get organic results
                    organic_results = data.get("organic_results", [])
                    
                    for item in organic_results[:num_results]:
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("link", ""),
                            "snippet": item.get("snippet", ""),
                            "displayed_link": item.get("displayed_link", ""),
                            "source_type": "web",
                            "api_source": "serpapi",
                            "retrieved_at": datetime.utcnow().isoformat()
                        })
                    
                    # Also include knowledge graph if available
                    knowledge_graph = data.get("knowledge_graph", {})
                    if knowledge_graph:
                        kg_result = {
                            "title": knowledge_graph.get("title", "Knowledge Graph Result"),
                            "url": knowledge_graph.get("website", knowledge_graph.get("source", {}).get("link", "")),
                            "snippet": knowledge_graph.get("description", ""),
                            "source_type": "knowledge_graph",
                            "api_source": "serpapi",
                            "retrieved_at": datetime.utcnow().isoformat()
                        }
                        if kg_result["url"]:
                            results.insert(0, kg_result)
                    
                else:
                    logger.error(f"SerpAPI search error: {response.status_code} - {response.text}")
                    
            logger.info(f"SerpAPI search returned {len(results)} results")
            
        except Exception as e:
            logger.error(f"SerpAPI search failed: {e}")
            
        # ── Cache store ──────────────────────────────────────────
        if results:
            await self._cache.set_search_cache("serpapi", cache_query, results[:num_results], self.CACHE_TTL)
        # ─────────────────────────────────────────────────────────
        return results[:num_results]
    
    async def duckduckgo_search(
        self,
        query: str,
        num_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search using DuckDuckGo via the duckduckgo-search library.
        Free, no API key required. Handles anti-bot measures internally.
        """
        cache_query = f"ddg:{query}:{num_results}"
        cached = await self._cache.get_search_cache("duckduckgo", cache_query)
        if cached is not None:
            return cached

        results = []
        try:
            from ddgs import DDGS

            # Run synchronous DDGS in a thread to avoid blocking the event loop
            def _do_search():
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=num_results))

            raw_results = await asyncio.get_event_loop().run_in_executor(None, _do_search)

            for item in raw_results:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("href", ""),
                    "snippet": item.get("body", ""),
                    "source_type": "web",
                    "api_source": "duckduckgo",
                    "retrieved_at": datetime.utcnow().isoformat(),
                })

            logger.info(f"DuckDuckGo search returned {len(results)} results")
        except ImportError:
            logger.error("duckduckgo-search library not installed. Run: pip install duckduckgo-search")
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")

        if results:
            await self._cache.set_search_cache("duckduckgo", cache_query, results[:num_results], self.CACHE_TTL)
        return results[:num_results]

    async def google_search(
        self,
        query: str,
        num_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search using Google Custom Search API.
        Phase 2: checks Redis cache first.
        """
        if not settings.google_api_key or not settings.google_search_engine_id:
            logger.warning("Google API credentials not configured")
            return []

        # ── Redis cache check ────────────────────────────────────
        cache_query = f"google:{query}:{num_results}"
        cached = await self._cache.get_search_cache("google", cache_query)
        if cached is not None:
            return cached
        # ─────────────────────────────────────────────────────────
        
        results = []
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                # Google allows max 10 results per request
                for start in range(1, min(num_results + 1, 101), 10):
                    params = {
                        "key": settings.google_api_key,
                        "cx": settings.google_search_engine_id,
                        "q": query,
                        "start": start,
                        "num": min(10, num_results - len(results))
                    }
                    
                    response = await client.get(
                        "https://www.googleapis.com/customsearch/v1",
                        params=params
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        items = data.get("items", [])
                        
                        for item in items:
                            results.append({
                                "title": item.get("title", ""),
                                "url": item.get("link", ""),
                                "snippet": item.get("snippet", ""),
                                "source_type": "web",
                                "api_source": "google",
                                "retrieved_at": datetime.utcnow().isoformat()
                            })
                    else:
                        logger.error(f"Google search error: {response.status_code}")
                        break
                        
                    if len(results) >= num_results:
                        break
                        
            logger.info(f"Google search returned {len(results)} results")
            
        except Exception as e:
            logger.error(f"Google search failed: {e}")

        # ── Cache store ──────────────────────────────────────────
        if results:
            await self._cache.set_search_cache("google", cache_query, results[:num_results], self.CACHE_TTL)
        # ─────────────────────────────────────────────────────────
        return results[:num_results]
    
    async def newsapi_search(
        self,
        query: str,
        num_results: int = 20,
        language: str = "en",
        sort_by: str = "relevancy"
    ) -> List[Dict[str, Any]]:
        """
        Search using NewsAPI for latest news articles.
        Phase 2: checks Redis cache first.
        """
        if not settings.newsapi_key:
            logger.warning("NewsAPI key not configured")
            return []

        # ── Redis cache check ────────────────────────────────────
        cache_query = f"newsapi:{query}:{num_results}:{sort_by}"
        cached = await self._cache.get_search_cache("newsapi", cache_query)
        if cached is not None:
            return cached
        # ─────────────────────────────────────────────────────────
        
        results = []
        
        try:
            # Limit to last 30 days to avoid stale/irrelevant results
            from_date = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=self.headers) as client:
                # Try /v2/everything first
                params = {
                    "q": query,
                    "language": language,
                    "sortBy": sort_by,
                    "pageSize": min(num_results, 100),
                    "from": from_date,
                    "apiKey": settings.newsapi_key
                }
                
                response = await client.get(
                    "https://newsapi.org/v2/everything",
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    api_status = data.get("status", "")
                    total_hits = data.get("totalResults", 0)
                    articles = data.get("articles", [])
                    
                    logger.info(f"NewsAPI response: status={api_status}, totalResults={total_hits}, articles_returned={len(articles)}")
                    
                    if total_hits > 0 and len(articles) == 0:
                        logger.warning(
                            "NewsAPI reports results exist but returned 0 articles — "
                            "possible free-plan restriction or rate limit"
                        )
                    
                    for article in articles:
                        results.append({
                            "title": article.get("title", ""),
                            "url": article.get("url", ""),
                            "snippet": article.get("description", ""),
                            "content": article.get("content", ""),
                            "author": article.get("author"),
                            "source_name": article.get("source", {}).get("name"),
                            "published_at": article.get("publishedAt"),
                            "source_type": "news",
                            "api_source": "newsapi",
                            "retrieved_at": datetime.utcnow().isoformat()
                        })
                elif response.status_code == 426:
                    logger.warning("NewsAPI /everything returned 426 — trying /top-headlines fallback")
                    # Fallback: top-headlines endpoint works on free plan
                    fallback_params = {
                        "q": query,
                        "language": language,
                        "pageSize": min(num_results, 100),
                        "apiKey": settings.newsapi_key,
                    }
                    fb_resp = await client.get(
                        "https://newsapi.org/v2/top-headlines",
                        params=fallback_params,
                    )
                    if fb_resp.status_code == 200:
                        fb_data = fb_resp.json()
                        for article in fb_data.get("articles", []):
                            results.append({
                                "title": article.get("title", ""),
                                "url": article.get("url", ""),
                                "snippet": article.get("description", ""),
                                "content": article.get("content", ""),
                                "author": article.get("author"),
                                "source_name": article.get("source", {}).get("name"),
                                "published_at": article.get("publishedAt"),
                                "source_type": "news",
                                "api_source": "newsapi",
                                "retrieved_at": datetime.utcnow().isoformat(),
                            })
                        logger.info(f"NewsAPI /top-headlines fallback returned {len(results)} results")
                    else:
                        logger.error(f"NewsAPI /top-headlines also failed: {fb_resp.status_code}")
                elif response.status_code == 429:
                    logger.error("NewsAPI rate limit exceeded (429)")
                else:
                    logger.error(f"NewsAPI error: {response.status_code} - {response.text[:300]}")
                    
            logger.info(f"NewsAPI returned {len(results)} results")
            
        except Exception as e:
            logger.error(f"NewsAPI search failed: {e}")

        # ── Cache store ──────────────────────────────────────────
        if results:
            await self._cache.set_search_cache("newsapi", cache_query, results, self.CACHE_TTL)
        # ─────────────────────────────────────────────────────────
        return results
    
    async def arxiv_search(
        self,
        query: str,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search ArXiv for academic papers.
        Phase 2: checks Redis cache first.
        """
        # ── Redis cache check ────────────────────────────────────
        cache_query = f"arxiv:{query}:{max_results}"
        cached = await self._cache.get_search_cache("arxiv", cache_query)
        if cached is not None:
            return cached
        # ─────────────────────────────────────────────────────────

        results = []
        
        try:
            # Build keyword-style query for ArXiv (strip natural language fluff)
            search_query = quote_plus(query)
            # Always use https — ArXiv 301-redirects http to https
            arxiv_base = settings.arxiv_api_base.replace("http://", "https://")
            url = f"{arxiv_base}?search_query=all:{search_query}&start=0&max_results={max_results}"
            
            # ArXiv rate-limits at 1 request / 3 seconds.  Acquire a
            # lightweight async lock to prevent concurrent calls from
            # violating the limit.
            if not hasattr(SearchTools, '_arxiv_lock'):
                SearchTools._arxiv_lock = asyncio.Lock()
                SearchTools._arxiv_last_call = 0.0

            async with SearchTools._arxiv_lock:
                import time
                since_last = time.monotonic() - SearchTools._arxiv_last_call
                if since_last < 3.0:
                    await asyncio.sleep(3.0 - since_last)

                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                    response = await client.get(url, headers=self.headers)

                SearchTools._arxiv_last_call = time.monotonic()
            
            if response.status_code == 200:
                # Parse Atom feed
                feed = feedparser.parse(response.text)
                
                for entry in feed.entries:
                    # Extract authors
                    authors = [author.get("name", "") for author in entry.get("authors", [])]
                    
                    # Get PDF link
                    pdf_link = ""
                    for link in entry.get("links", []):
                        if link.get("type") == "application/pdf":
                            pdf_link = link.get("href", "")
                            break
                    
                    results.append({
                        "title": entry.get("title", "").replace("\n", " "),
                        "url": entry.get("link", ""),
                        "pdf_url": pdf_link,
                        "snippet": entry.get("summary", "").replace("\n", " ")[:500],
                        "authors": authors,
                        "published_at": entry.get("published"),
                        "updated_at": entry.get("updated"),
                        "categories": [tag.get("term") for tag in entry.get("tags", [])],
                        "arxiv_id": entry.get("id", "").split("/abs/")[-1],
                        "source_type": "academic",
                        "api_source": "arxiv",
                        "retrieved_at": datetime.utcnow().isoformat()
                    })
            elif response.status_code == 503:
                logger.warning(f"ArXiv rate-limited (503) for query: {query[:60]}")
                sentry_sdk.capture_message(
                    f"ArXiv 503 rate-limit for: {query[:120]}",
                    level="warning",
                )
            else:
                logger.error(f"ArXiv search error: HTTP {response.status_code} — {response.text[:200]}")
                    
            logger.info(f"ArXiv search returned {len(results)} results")
            
        except Exception as e:
            logger.error(f"ArXiv search failed: {e}")

        # ── Cache store ──────────────────────────────────────────
        if results:
            await self._cache.set_search_cache("arxiv", cache_query, results, self.CACHE_TTL)
        # ─────────────────────────────────────────────────────────
        return results
    
    async def pubmed_search(
        self,
        query: str,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search PubMed for medical/scientific research.
        Phase 2: checks Redis cache first.
        """
        # ── Redis cache check ────────────────────────────────────
        cache_query = f"pubmed:{query}:{max_results}"
        cached = await self._cache.get_search_cache("pubmed", cache_query)
        if cached is not None:
            return cached
        # ─────────────────────────────────────────────────────────

        results = []
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=self.headers) as client:
                # Step 1: Search for IDs
                search_params = {
                    "db": "pubmed",
                    "term": query,
                    "retmax": max_results,
                    "retmode": "json",
                    "sort": "relevance"
                }
                
                search_response = await client.get(
                    f"{settings.pubmed_api_base}/esearch.fcgi",
                    params=search_params
                )
                
                if search_response.status_code != 200:
                    logger.error(f"PubMed search error: {search_response.status_code}")
                    return results
                
                search_data = search_response.json()
                id_list = search_data.get("esearchresult", {}).get("idlist", [])
                
                if not id_list:
                    return results
                
                # Step 2: Fetch details for each ID
                fetch_params = {
                    "db": "pubmed",
                    "id": ",".join(id_list),
                    "retmode": "xml"
                }
                
                fetch_response = await client.get(
                    f"{settings.pubmed_api_base}/efetch.fcgi",
                    params=fetch_params
                )
                
                if fetch_response.status_code == 200:
                    # Parse XML response
                    root = ET.fromstring(fetch_response.text)
                    
                    for article in root.findall(".//PubmedArticle"):
                        try:
                            medline = article.find(".//MedlineCitation")
                            article_data = medline.find(".//Article") if medline is not None else None
                            
                            if article_data is None:
                                continue
                            
                            # Extract title
                            title_elem = article_data.find(".//ArticleTitle")
                            title = title_elem.text if title_elem is not None else ""
                            
                            # Extract abstract
                            abstract_elem = article_data.find(".//Abstract/AbstractText")
                            abstract = abstract_elem.text if abstract_elem is not None else ""
                            
                            # Extract authors
                            authors = []
                            for author in article_data.findall(".//Author"):
                                last_name = author.find("LastName")
                                first_name = author.find("ForeName")
                                if last_name is not None:
                                    name = last_name.text
                                    if first_name is not None:
                                        name = f"{first_name.text} {name}"
                                    authors.append(name)
                            
                            # Extract PMID
                            pmid_elem = medline.find(".//PMID")
                            pmid = pmid_elem.text if pmid_elem is not None else ""
                            
                            # Extract publication date
                            pub_date = article_data.find(".//PubDate")
                            year = pub_date.find("Year").text if pub_date is not None and pub_date.find("Year") is not None else ""
                            
                            results.append({
                                "title": title,
                                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                                "snippet": abstract[:500] if abstract else "",
                                "authors": authors,
                                "pmid": pmid,
                                "published_at": year,
                                "source_type": "academic",
                                "api_source": "pubmed",
                                "retrieved_at": datetime.utcnow().isoformat()
                            })
                        except Exception as e:
                            logger.warning(f"Error parsing PubMed article: {e}")
                            continue
                            
            logger.info(f"PubMed search returned {len(results)} results")
            
        except Exception as e:
            logger.error(f"PubMed search failed: {e}")

        # ── Cache store ──────────────────────────────────────────
        if results:
            await self._cache.set_search_cache("pubmed", cache_query, results, self.CACHE_TTL)
        # ─────────────────────────────────────────────────────────
        return results
    
    async def wikipedia_search(
        self,
        query: str,
        num_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search Wikipedia for general knowledge.
        Phase 2: checks Redis cache first.
        """
        # ── Redis cache check ────────────────────────────────────
        cache_query = f"wikipedia:{query}:{num_results}"
        cached = await self._cache.get_search_cache("wikipedia", cache_query)
        if cached is not None:
            return cached
        # ─────────────────────────────────────────────────────────

        results = []
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=self.headers) as client:
                # Search for pages
                search_params = {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": num_results,
                    "format": "json"
                }
                
                search_response = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params=search_params
                )
                
                if search_response.status_code != 200:
                    logger.error(f"Wikipedia search API error: HTTP {search_response.status_code}")
                    return results
                
                search_data = search_response.json()
                pages = search_data.get("query", {}).get("search", [])
                logger.info(f"Wikipedia search found {len(pages)} pages for: {query[:60]}")
                
                # Get summaries for each page
                for page in pages:
                    title = page.get("title", "")
                    
                    try:
                        # Get page summary — use underscores, NOT quote_plus
                        # (the REST API returns 404 for spaces encoded as +)
                        title_slug = title.replace(" ", "_")
                        summary_response = await client.get(
                            f"{settings.wikipedia_api_base}/page/summary/{title_slug}"
                        )
                        
                        if summary_response.status_code == 200:
                            summary_data = summary_response.json()
                            
                            results.append({
                                "title": summary_data.get("title", title),
                                "url": summary_data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                                "snippet": summary_data.get("extract", ""),
                                "description": summary_data.get("description", ""),
                                "source_type": "wikipedia",
                                "api_source": "wikipedia",
                                "retrieved_at": datetime.utcnow().isoformat()
                            })
                        else:
                            logger.warning(f"Wikipedia summary fetch failed for '{title}': HTTP {summary_response.status_code}")
                            # Still include the page with search snippet as fallback
                            snippet_html = page.get("snippet", "")
                            import re as _re
                            snippet_clean = _re.sub(r'<[^>]+>', '', snippet_html)
                            results.append({
                                "title": title,
                                "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                                "snippet": snippet_clean,
                                "description": "",
                                "source_type": "wikipedia",
                                "api_source": "wikipedia",
                                "retrieved_at": datetime.utcnow().isoformat()
                            })
                    except Exception as page_err:
                        logger.warning(f"Wikipedia page '{title}' fetch error: {page_err}")
                        
            logger.info(f"Wikipedia search returned {len(results)} results")
            
        except Exception as e:
            logger.error(f"Wikipedia search failed: {e}")

        # ── Cache store ──────────────────────────────────────────
        if results:
            await self._cache.set_search_cache("wikipedia", cache_query, results, self.CACHE_TTL)
        # ─────────────────────────────────────────────────────────
        return results
    
    async def fetch_full_content(self, url: str) -> Optional[str]:
        """
        Fetch full content from a URL.
        
        Args:
            url: URL to fetch
            
        Returns:
            Extracted text content or None
        """
        try:
            from bs4 import BeautifulSoup
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self.headers, follow_redirects=True)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'lxml')
                    
                    # Remove script and style elements
                    for script in soup(["script", "style", "nav", "footer", "header"]):
                        script.decompose()
                    
                    # Get text
                    text = soup.get_text(separator='\n', strip=True)
                    
                    # Clean up whitespace
                    lines = [line.strip() for line in text.splitlines() if line.strip()]
                    return '\n'.join(lines)
                    
        except Exception as e:
            logger.error(f"Failed to fetch content from {url}: {e}")
            
        return None


# Singleton instance
search_tools = SearchTools()
