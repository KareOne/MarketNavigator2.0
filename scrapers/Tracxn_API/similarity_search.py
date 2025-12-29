"""
Similarity Search for TracXN Companies
This module provides functionality to find similar companies based on description
"""
import json
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict


def find_similar_companies(
    companies_json: str,
    target_description: str,
    top_k: int = None,
    model_name: str = "all-MiniLM-L6-v2"
) -> List[Dict]:
    """
    Find and rank companies by similarity to a target description.
    
    Args:
        companies_json: JSON string containing list of companies with their descriptions.
                       Expected format: [
                           {
                               "name": "Company A",
                               "description": "Description of Company A",
                               ... (other optional fields)
                           },
                           ...
                       ]
        target_description: The target description to compare against
        top_k: Number of top results to return (None returns all)
        model_name: The sentence-transformer model to use for embeddings
                   (default: "all-MiniLM-L6-v2")
    
    Returns:
        List of companies sorted by similarity score (highest first)
        Each company dict includes:
        - All original fields from input JSON
        - similarity_score: cosine similarity score (0-1)
        - rank: position in the sorted list (1-indexed)
    """
    # Load the embedding model
    print(f"Loading embedding model: {model_name}")
    model = SentenceTransformer(model_name)
    
    # Parse the JSON input
    try:
        companies = json.loads(companies_json)
        if not isinstance(companies, list):
            raise ValueError("JSON must contain a list of companies")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")
    
    if not companies:
        return []
    
    print(f"Processing {len(companies)} companies...")
    
    # Extract descriptions from companies
    descriptions = []
    for company in companies:
        desc = company.get('description') or company.get('detailedDescription') or company.get('about', '')
        if not desc:
            # If no description field, create one from available fields
            company_name = company.get('name', 'Unknown')
            desc = f"{company_name}"
        descriptions.append(desc)
    
    # Generate embeddings for all companies
    print("Generating embeddings for companies...")
    company_embeddings = model.encode(descriptions, show_progress_bar=True, batch_size=32)
    
    # Generate embedding for target description
    print("Generating embedding for target description...")
    target_embedding = model.encode([target_description])
    
    # Calculate cosine similarity between target and all companies
    print("Calculating similarity scores...")
    similarities = cosine_similarity(target_embedding, company_embeddings)[0]
    
    # Add similarity scores to companies
    results = []
    for i, company in enumerate(companies):
        company_result = company.copy()
        company_result['similarity_score'] = float(similarities[i])
        results.append(company_result)
    
    # Sort by similarity score (descending)
    results.sort(key=lambda x: x['similarity_score'], reverse=True)
    
    # Add rank
    for i, company in enumerate(results):
        company['rank'] = i + 1
    
    # Return top_k results if specified
    if top_k is not None:
        results = results[:top_k]
    
    print(f"\nReturning {len(results)} sorted companies")
    if results:
        company_name = results[0].get('name', 'N/A')
        print(f"Top result: {company_name} (similarity: {results[0]['similarity_score']:.4f})")
    
    return results
