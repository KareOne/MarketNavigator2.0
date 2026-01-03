"""
Similarity Search for Crunchbase Companies
This module provides functionality to find similar companies based on description
"""
import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict

# Local model path - try container path first, then relative path
LOCAL_MODEL_PATHS = [
    "/app/models/all-MiniLM-L6-v2",  # Docker container path
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "all-MiniLM-L6-v2"),  # Relative to this file
]

def _get_model_path(model_name: str) -> str:
    """Get the local model path if available, otherwise return model name for download."""
    if model_name == "all-MiniLM-L6-v2":
        for path in LOCAL_MODEL_PATHS:
            if os.path.exists(path):
                print(f"Using local model from: {path}")
                return path
    # Fall back to downloading from HuggingFace
    print(f"Local model not found, will download: {model_name}")
    return model_name


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
                               "company_name": "Company A",
                               "description": "Description of Company A",
                               ... (other optional fields)
                           },
                           ...
                       ]
        target_description: The target description to compare against
        top_k: Number of top results to return (None returns all)
        model_name: The sentence-transformer model to use for embeddings
                   (default: "all-MiniLM-L6-v2" - same as in generate_crunchbase_embeddings.py)
    
    Returns:
        List of companies sorted by similarity score (highest first)
        Each company dict includes:
        - All original fields from input JSON
        - similarity_score: cosine similarity score (0-1)
        - rank: position in the sorted list (1-indexed)
    
    Example:
        companies_json = '''[
            {"company_name": "TechCo", "description": "AI-powered analytics platform"},
            {"company_name": "HealthApp", "description": "Healthcare mobile application"}
        ]'''
        
        target = "Machine learning and data analytics solutions"
        results = find_similar_companies(companies_json, target, top_k=5)
    """
    # Load the embedding model - try local path first
    model_path = _get_model_path(model_name)
    print(f"Loading embedding model: {model_path}")
    model = SentenceTransformer(model_path)
    
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
    # Handle both 'description' and 'about' fields (common in Crunchbase data)
    descriptions = []
    for company in companies:
        desc = company.get('description') or company.get('about') or company.get('About') or company.get('combined_text', '')
        if not desc:
            # If no description field, create one from available fields
            company_name = company.get('company_name') or company.get('Company Name', 'Unknown')
            industry = company.get('industry') or company.get('Company Type', '')
            desc = f"{company_name}. {industry}"
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
        company_name = results[0].get('company_name') or results[0].get('Company Name', 'N/A')
        print(f"Top result: {company_name} (similarity: {results[0]['similarity_score']:.4f})")
    
    return results


def find_similar_companies_from_file(
    json_file_path: str,
    target_description: str,
    top_k: int = None,
    model_name: str = "all-MiniLM-L6-v2"
) -> List[Dict]:
    """
    Convenience function to load companies from a JSON file and find similar ones.
    
    Args:
        json_file_path: Path to JSON file containing companies
        target_description: The target description to compare against
        top_k: Number of top results to return (None returns all)
        model_name: The sentence-transformer model to use
    
    Returns:
        List of companies sorted by similarity score
    """
    print(f"Loading companies from: {json_file_path}")
    with open(json_file_path, 'r', encoding='utf-8') as f:
        companies_json = f.read()
    
    return find_similar_companies(companies_json, target_description, top_k, model_name)
