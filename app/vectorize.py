import pandas as pd
import numpy as np
import json
try:
    from sentence_transformers import SentenceTransformer
    import torch
    torch_available = True
except ImportError:
    SentenceTransformer = None
    torch = None
    torch_available = False
from scipy.spatial.distance import cosine
from .models import Product, users, SearchHistory, ViewHistory
from django.db.models import Count
from django.utils import timezone



model = SentenceTransformer('all-MiniLM-L6-v2') if SentenceTransformer else None

def process_reviews(reviews):
    if not model or not reviews or not isinstance(reviews, list) or len(reviews) == 0:
        return None
    try:
        review_vectors = model.encode(reviews)
        return review_vectors.mean(axis=0)
    except Exception:
        return None

def process_search(search_queries):
    if not model or not search_queries or not isinstance(search_queries, list) or len(search_queries) == 0:
        return None
    try:
        search_vectors = model.encode(search_queries)
        return search_vectors.mean(axis=0)
    except Exception:
        return None

def combine_product_with_reviews(product):
    if not model:
        return None
    try:
        combined_text = (
            f"Product Name: {product.name}, Rating: {product.rating}, "
            f"Category: {product.category}, Description: {product.description}"
        )
        product_vector = model.encode(combined_text)
        reviews = [review.description for review in product.reviews_set.all()]
        review_vector = process_reviews(reviews)
        combined_vector = product_vector + review_vector if review_vector is not None else product_vector
        return combined_vector
    except Exception:
        return None

def vectorize_product_with_reviews(df):
    if not model:
        return []
    vectors = []
    try:
        for _, row in df.iterrows():
            combined_text = (
                f"Product Name: {row['name']}, Rating: {row['rating']}, "
                f"Category: {row['category']}, Description: {row['description']}"
            )
            product_vector = model.encode(combined_text)
            review_vector = process_reviews([row['reviews']] if row['reviews'] else [])
            combined_vector = product_vector + review_vector if review_vector is not None else product_vector
            vectors.append(combined_vector)
    except Exception:
        return []
    return vectors

def combine_user_with_search_and_views(user):
    if not model:
        return None
    try:
        combined_text = f"User: {user.user.username}"
        user_vector = model.encode(combined_text)
        search_queries = [sh.query for sh in SearchHistory.objects.filter(user=user)]
        search_vector = process_search(search_queries)
        viewed_products = [
            f"{vp.product.name} {vp.product.category} {vp.product.description}"
            for vp in ViewHistory.objects.filter(user=user)
        ]
        view_vector = process_reviews(viewed_products)
        combined_vector = user_vector
        if search_vector is not None:
            combined_vector += search_vector
        if view_vector is not None:
            combined_vector += view_vector
        return combined_vector
    except Exception:
        return None

def vectorize_all_products():
    if not model:
        return
    products = Product.objects.all()
    for product in products:
        try:
            vector = combine_product_with_reviews(product)
            if vector is not None:
                product.vector_data = json.dumps(vector.tolist())
                product.save()
        except Exception:
            continue

def vectorize_all_users():
    if not model:
        return
    users_list = users.objects.all()
    for user in users_list:
        try:
            vector = combine_user_with_search_and_views(user)
            if vector is not None:
                user.vector_data = json.dumps(vector.tolist())
                user.save()
        except Exception:
            continue

def vectorize_single_user(user):
    if not model:
        return
    try:
        user_obj = users.objects.get(user=user)
        vector = combine_user_with_search_and_views(user_obj)
        if vector is not None:
            user_obj.vector_data = json.dumps(vector.tolist())
            user_obj.save()
    except users.DoesNotExist:
        pass
    except Exception:
        pass

def get_recommendations(user, top_n=5):
    if not model or not torch_available:
        return list(Product.objects.order_by('?')[:top_n])

    try:
        user_obj = users.objects.get(user=user)
        user_vector = np.array(json.loads(user_obj.vector_data)) if user_obj.vector_data else None
        if user_vector is None:
            return list(Product.objects.order_by('?')[:top_n])

        recommendations = []
        # Step 1: Get all products and annotate with review count
        products = Product.objects.all().annotate(review_count=Count('reviews_set'))

        # Step 2: Get the most recent search query
        latest_search = SearchHistory.objects.filter(user=user_obj).order_by('-id').first()
        # Step 3: Prioritize products matching the latest search query
        if latest_search:
            query = latest_search.query.lower()
            # Find products matching the search query (name or description)
            matching_products = products.filter(name__icontains=query) | products.filter(description__icontains=query)
            # Add matching products with highest score
            recommendations.extend([(product, 1.0) for product in matching_products.order_by('-review_count')])

            # Get categories of matching products
            search_categories = set(matching_products.values_list('category', flat=True))
            # Add other products from the same category
            if search_categories:
                category_products = products.filter(category__in=search_categories).exclude(
                    id__in=matching_products.values_list('id', flat=True)
                ).order_by('-review_count')
                for product in category_products:
                    if not any(p.id == product.id for p, _ in recommendations):
                        recommendations.append((product, 0.9))  # Slightly lower score than search matches

        # Step 4: Prioritize the most recently viewed product
        viewed_products = ViewHistory.objects.filter(user=user_obj).order_by('-id')[:5]  # Limit to recent 5 views
        viewed_product_ids = set(vp.product.id for vp in viewed_products)
        viewed_categories = set(vp.product.category for vp in viewed_products)

        # Add the most recently viewed product with highest score
        latest_view = viewed_products.first()  # Most recent view
        if latest_view:
            latest_viewed_product = products.filter(id=latest_view.product.id).first()
            if latest_viewed_product and not any(p.id == latest_viewed_product.id for p, _ in recommendations):
                recommendations.append((latest_viewed_product, 1.0))  # Same score as search matches

        # Add other recently viewed products (excluding the latest one)
        other_viewed_products = products.filter(id__in=viewed_product_ids).exclude(
            id=latest_view.product.id if latest_view else None
        ).order_by('-review_count')
        for product in other_viewed_products:
            if not any(p.id == product.id for p, _ in recommendations):
                recommendations.append((product, 0.9))  # Same score as search category

        # Add products from viewed categories
        if viewed_categories:
            viewed_category_products = products.filter(category__in=viewed_categories).exclude(
                id__in=viewed_product_ids
            ).exclude(id__in=[p.id for p, _ in recommendations]).order_by('-review_count')
            recommendations.extend([(product, 0.85) for product in viewed_category_products])

        # Step 5: Add remaining products with cosine similarity
        remaining_products = products.exclude(id__in=[rec[0].id for rec in recommendations])
        for product in remaining_products:
            if product.vector_data:
                try:
                    product_vector = np.array(json.loads(product.vector_data))
                    similarity = 1 - cosine(user_vector, product_vector)
                    if not np.isnan(similarity):
                        recommendations.append((product, similarity))
                except (json.JSONDecodeError, Exception):
                    continue

        # Step 6: Sort recommendations by score and review count
        recommendations.sort(key=lambda x: (x[1], x[0].review_count), reverse=True)

        # Step 7: Return top_n products
        return [rec[0] for rec in recommendations[:top_n]]

    except (users.DoesNotExist, Exception):
        return list(Product.objects.order_by('?')[:top_n])