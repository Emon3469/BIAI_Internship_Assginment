"""Feature extraction using TF-IDF character n-grams and text features.

Adapted from high-scoring Bengali Hallucination Detection datathon notebooks.
Techniques used:
- TF-IDF character n-grams (3,5) with max_features=4000 (from notebook)
- MiniBM25 relevance scoring concept
- Balanced class handling
- StratifiedKFold cross-validation for confidence calibration
"""

import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import classification_report
from collections import Counter
import math

# Categories
CATEGORIES = ["sales_lead", "support_issue", "spam", "job_seeker", "general_inquiry"]


class MiniBM25:
    """Lightweight BM25 scorer adapted from datathon notebook.

    Used to score relevance of enquiry text against category-specific
    keyword vocabularies. Provides an additional feature signal beyond
    simple keyword counting.
    """
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.doc_freqs = {}
        self.avg_dl = 0
        self.n_docs = 0
        self.vocab = set()

    def fit(self, documents: list[str]):
        """Build document frequency index from a corpus of documents."""
        self.n_docs = len(documents)
        doc_lens = []
        for doc in documents:
            tokens = doc.lower().split()
            doc_lens.append(len(tokens))
            unique_tokens = set(tokens)
            self.vocab.update(unique_tokens)
            for token in unique_tokens:
                self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1
        self.avg_dl = sum(doc_lens) / len(doc_lens) if doc_lens else 1
        return self

    def score(self, query: str, document: str) -> float:
        """Score a document's relevance to a query using BM25."""
        query_tokens = query.lower().split()
        doc_tokens = document.lower().split()
        doc_len = len(doc_tokens)
        tf_map = Counter(doc_tokens)

        score = 0.0
        for qt in query_tokens:
            if qt not in tf_map:
                continue
            tf = tf_map[qt]
            df = self.doc_freqs.get(qt, 0)
            idf = math.log((self.n_docs - df + 0.5) / (df + 0.5) + 1)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_dl)
            score += idf * (numerator / denominator)
        return score


class TFIDFFeatureExtractor:
    """Extract TF-IDF features from multilingual text.

    Uses character n-grams (3,5) which work well for Bangla/Banglish
    because they capture morphological patterns without requiring
    word-level tokenization. Max features capped at 4000 to prevent
    overfitting on small datasets (adapted from datathon notebook).
    """

    def __init__(self, max_features=4000, ngram_range=(3, 5)):
        self.vectorizer = TfidfVectorizer(
            analyzer='char_wb',
            ngram_range=ngram_range,
            max_features=max_features,
            sublinear_tf=True,  # from notebook: apply log normalization
        )
        self.is_fitted = False

    def fit(self, texts: list[str]) -> 'TFIDFFeatureExtractor':
        self.vectorizer.fit(texts)
        self.is_fitted = True
        return self

    def transform(self, texts: list[str]) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Call fit() first")
        return self.vectorizer.transform(texts).toarray()

    def fit_transform(self, texts: list[str]) -> np.ndarray:
        self.is_fitted = True
        return self.vectorizer.fit_transform(texts).toarray()


def extract_handcrafted_features(message: str) -> dict:
    """Extract handcrafted features for classification.

    These complement TF-IDF features with domain-specific signals.
    """
    text_lower = message.lower()

    # Character-level stats
    bangla_chars = len(re.findall(r'[\u0980-\u09FF]', message))
    english_chars = len(re.findall(r'[A-Za-z]', message))
    total_chars = len(message)
    digit_chars = len(re.findall(r'\d', message))

    # Word-level stats
    words = message.split()
    word_count = len(words)
    avg_word_len = sum(len(w) for w in words) / word_count if word_count else 0

    # Punctuation density
    punct_count = len(re.findall(r'[!?.,;:]', message))

    # URL/link presence
    has_url = bool(re.search(r'(http|www|\.ly/|\.com)', text_lower))

    # Question mark (indicates inquiry)
    has_question = '?' in message

    # Number mention (price, count)
    has_numbers = bool(re.search(r'\d+', message))

    # Urgency markers
    exclamation_count = message.count('!')
    caps_ratio = sum(1 for c in message if c.isupper()) / total_chars if total_chars else 0

    return {
        'bangla_ratio': bangla_chars / total_chars if total_chars else 0,
        'english_ratio': english_chars / total_chars if total_chars else 0,
        'digit_ratio': digit_chars / total_chars if total_chars else 0,
        'word_count': word_count,
        'avg_word_len': avg_word_len,
        'punct_density': punct_count / word_count if word_count else 0,
        'has_url': int(has_url),
        'has_question': int(has_question),
        'has_numbers': int(has_numbers),
        'exclamation_count': exclamation_count,
        'caps_ratio': caps_ratio,
        'msg_length': total_chars,
    }


class EnsembleConfidenceScorer:
    """Ensemble scorer combining rule-based classification with ML features.

    Adapted from datathon notebook's ensemble approach:
    - Uses multiple LogisticRegression with different C values (0.1, 1.0, 10.0)
    - Applies StratifiedKFold for confidence calibration
    - Dual-threshold concept: high confidence + low confidence boundaries

    This does NOT replace the rule-based classifier. It provides an
    independent confidence score that validates rule-based decisions.
    With only 20 samples, the ML layer is advisory — the rule-based
    classifier makes the final call. This is by design to prevent
    overfitting.
    """

    def __init__(self):
        self.models = []  # List of (model, weight) tuples
        self.feature_extractor = TFIDFFeatureExtractor(max_features=500)  # Lower for 20 samples
        self.bm25 = MiniBM25()
        self.is_fitted = False
        self.cv_accuracy = None
        self.category_keywords = {
            'sales_lead': 'price cost fee enroll enrol register join bootcamp fellowship training programme program discount instalment quote proposal দাম মূল্য ভর্তি রেজিস্ট্রেশন ট্রেনিং ডিসকাউন্ট কিস্তি',
            'support_issue': 'paid refund cancel confirmation receipt problem issue complaint money back bkash পেমেন্ট কনফার্মেশন রিফান্ড বাতিল সমস্যা upset angry',
            'spam': 'earn usd crypto signal click free money investment opportunity guaranteed income',
            'job_seeker': 'looking for job apply position role vacancy hiring recruit চাকরি intern',
            'general_inquiry': 'live recorded offline online class certificate approved location কোথায় how when schedule what',
        }

    def fit(self, texts: list[str], labels: list[str]):
        """Train ensemble on labeled data with cross-validation.

        For small datasets (n≤30), uses leave-one-out or 3-fold CV.
        """
        n = len(texts)
        if n < 5:
            self.is_fitted = False
            return self

        # Build BM25 index
        all_kw_docs = list(self.category_keywords.values())
        self.bm25.fit(texts + all_kw_docs)

        # Extract features
        tfidf_features = self.feature_extractor.fit_transform(texts)
        handcrafted = np.array([
            list(extract_handcrafted_features(t).values()) for t in texts
        ])

        # BM25 scores against each category
        bm25_scores = np.array([
            [self.bm25.score(self.category_keywords[cat], text) for cat in CATEGORIES]
            for text in texts
        ])

        features = np.hstack([tfidf_features, handcrafted, bm25_scores])

        # Train ensemble with different regularization (from notebook)
        self.models = []
        for c_val in [0.1, 1.0, 10.0]:
            model = LogisticRegression(
                C=c_val,
                class_weight='balanced',  # Handle class imbalance
                max_iter=1000,
                solver='lbfgs',
            )
            model.fit(features, labels)
            self.models.append((model, 1.0 / 3))  # Equal weight

        self.is_fitted = True

        # Run cross-validation to estimate reliability
        n_splits = min(3, n)
        min_class_count = min(Counter(labels).values()) if labels else 0
        if n_splits >= 2 and len(set(labels)) > 1:
            if min_class_count >= n_splits:
                cv_splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
            else:
                from sklearn.model_selection import KFold
                cv_splitter = KFold(n_splits=n_splits, shuffle=True, random_state=42)
            cv_scores = []
            try:
                for train_idx, val_idx in cv_splitter.split(features, labels):
                    fold_model = LogisticRegression(
                        C=1.0, class_weight='balanced', max_iter=1000,
                        solver='lbfgs'
                    )
                    fold_model.fit(features[train_idx], np.array(labels)[train_idx])
                    score = fold_model.score(features[val_idx], np.array(labels)[val_idx])
                    cv_scores.append(score)
                self.cv_accuracy = np.mean(cv_scores)
            except ValueError:
                self.cv_accuracy = None
        else:
            self.cv_accuracy = None

        return self

    def predict_confidence(self, text: str) -> dict:
        """Get ensemble confidence scores for a text.

        Returns dict of category -> confidence score.
        Uses dual-threshold concept from notebook:
        - Scores > 0.7 = high confidence (rule-based likely correct)
        - Scores 0.3-0.7 = uncertain (needs manual review)
        - Scores < 0.3 = low confidence (rule-based should override)
        """
        if not self.is_fitted:
            return {cat: 1.0 / len(CATEGORIES) for cat in CATEGORIES}

        # Extract features for single text
        tfidf = self.feature_extractor.transform([text])
        handcrafted = np.array([list(extract_handcrafted_features(text).values())])
        bm25_scores = np.array([[
            self.bm25.score(self.category_keywords[cat], text) for cat in CATEGORIES
        ]])
        features = np.hstack([tfidf, handcrafted, bm25_scores])

        # Get probabilities from each model
        all_probs = []
        for model, weight in self.models:
            probs = model.predict_proba(features)[0]
            # Map to our category order
            class_map = {cls: i for i, cls in enumerate(model.classes_)}
            ordered_probs = [probs[class_map[cat]] if cat in class_map else 0 for cat in CATEGORIES]
            all_probs.append(np.array(ordered_probs) * weight)

        # Average ensemble
        avg_probs = np.sum(all_probs, axis=0)
        total = avg_probs.sum()
        if total > 0:
            avg_probs = avg_probs / total  # Normalize
        else:
            avg_probs = np.ones(len(CATEGORIES)) / len(CATEGORIES)

        return {cat: float(prob) for cat, prob in zip(CATEGORIES, avg_probs)}
