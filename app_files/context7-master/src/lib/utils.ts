import { SearchResponse, SearchResult } from "./types.js";

/**
 * Format a search result into a string representation
 * @param result SearchResult to format
 * @returns Formatted search result string
 */
export function formatSearchResult(result: SearchResult): string {
  return `- Title: ${result.title}
- Context7-compatible library ID: ${result.id}
- Description: ${result.description}
- Code Snippets: ${result.totalSnippets}
- GitHub Stars: ${result.stars}`;
}

/**
 * Format search results into a string representation
 * @param searchResponse The search response to format
 * @returns Formatted search results string
 */
export function formatSearchResults(searchResponse: SearchResponse): string {
  if (!searchResponse.results || searchResponse.results.length === 0) {
    return "No documentation libraries found matching your query.";
  }

  const formattedResults = searchResponse.results.map(formatSearchResult);
  return formattedResults.join("\n---\n");
}
