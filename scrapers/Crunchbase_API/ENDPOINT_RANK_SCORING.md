# Crunchbase API - Combined Rank & Similarity Scoring

## New Endpoint: `/search/crunchbase/top-similar-with-rank`

This endpoint combines AI-powered similarity scoring with Crunchbase rank scoring to find the most relevant companies.

### How It Works

1. **Collection Phase**: Collects companies from multiple keyword searches, including:
   - Company URL
   - Full description
   - Crunchbase rank (from `rank_org_company` column)

2. **Scoring Phase**:
   - **Similarity Score** (0-1): AI-powered comparison against target description
   - **Rank Score** (0-1): Normalized CB rank where:
     - `1.0` = Best rank (lowest number) in the result set
     - `0.0` = Worst rank (highest number) in the result set
   - **Combined Score**: Weighted sum of both scores

3. **Ranking**: Companies are sorted by combined score (default: 75% similarity + 25% rank)

4. **Scraping**: Only the top N companies are scraped for full data

### Request Body

```json
{
  "keywords": ["AI", "machine learning"],
  "num_companies": 10,
  "days_threshold": 15,
  "top_count": 10,
  "target_description": "AI company focused on healthcare",
  "similarity_weight": 0.75,
  "rank_weight": 0.25
}
```

### Parameters

- `keywords`: List of keywords to search (required)
- `num_companies`: Companies to collect per keyword (default: 10)
- `days_threshold`: Days before re-scraping (default: 15)
- `top_count`: Number of top companies to scrape fully (default: 10)
- `target_description`: Target description for similarity comparison (required)
- `similarity_weight`: Weight for similarity score, 0-1 (default: 0.75)
- `rank_weight`: Weight for rank score, 0-1 (default: 0.25)

**Note**: `similarity_weight + rank_weight` must equal 1.0

### Response Structure

```json
{
  "all_companies": [
    {
      "url": "...",
      "description": "...",
      "similarity_score": 0.95,
      "cb_rank": 123,
      "rank_score": 0.87,
      "combined_score": 0.93,
      "combined_rank": 1,
      "appearance_count": 3,
      "keywords": ["AI", "healthcare"]
    }
  ],
  "top_companies_full_data": [
    {
      "company_data": { /* full scraped data */ },
      "similarity_score": 0.95,
      "cb_rank": 123,
      "rank_score": 0.87,
      "combined_score": 0.93,
      "combined_rank": 1,
      "appearance_count": 3,
      "keywords": ["AI", "healthcare"],
      "url": "..."
    }
  ],
  "metadata": {
    "total_keywords_searched": 2,
    "successful_keywords": 2,
    "failed_keywords": 0,
    "total_unique_companies": 50,
    "all_companies_count": 50,
    "top_count_requested": 10,
    "top_count_returned": 10,
    "target_description": "...",
    "cb_rank_range": {
      "min_rank": 1,
      "max_rank": 5000,
      "range": 4999
    },
    "weights": {
      "similarity_weight": 0.75,
      "rank_weight": 0.25
    },
    "collection_time_seconds": 45.2,
    "similarity_time_seconds": 2.3,
    "scraping_time_seconds": 120.5,
    "total_time_seconds": 168.0
  }
}
```

### Key Features

- **Comprehensive Results**: Returns ALL companies sorted by combined score
- **Smart Ranking**: Balances relevance (similarity) with authority (CB rank)
- **Efficient**: Only scrapes full data for top companies
- **Flexible Weights**: Adjust the importance of similarity vs. rank
- **Detailed Metadata**: Includes timing, rank ranges, and statistics

### Use Cases

1. **Balanced Search**: Default 75/25 split for relevance with some weight on prominence
2. **Relevance-First**: 90/10 split to prioritize description similarity
3. **Authority-First**: 50/50 or 40/60 split to give more weight to CB rank
4. **Pure Relevance**: 100/0 split (same as `/top-similar-full` endpoint)

### Example Request

```bash
curl -X POST "http://localhost:8003/search/crunchbase/top-similar-with-rank" \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": ["artificial intelligence", "healthcare"],
    "num_companies": 20,
    "top_count": 10,
    "target_description": "AI-powered healthcare platform for diagnostics",
    "similarity_weight": 0.8,
    "rank_weight": 0.2
  }'
```

## Implementation Details

### New Function in `search_tag.py`

`collect_companies_with_rank(search_hashtag, num_companies=5)`:
- Collects URLs, descriptions, and CB rank from search results
- Extracts rank from `grid-cell[data-columnid="rank_org_company"]`
- Returns list of dicts with `url`, `description`, and `cb_rank`

### Rank Score Calculation

```python
rank_score = 1.0 - ((cb_rank - min_rank) / rank_range)
```

Where:
- `min_rank`: Lowest CB rank number in results (best)
- `max_rank`: Highest CB rank number in results (worst)
- `rank_range`: max_rank - min_rank

### Combined Score Calculation

```python
combined_score = (similarity_score * similarity_weight) + (rank_score * rank_weight)
```

Companies are then sorted by `combined_score` in descending order.
