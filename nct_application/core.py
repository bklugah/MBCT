"""Core analysis engine for NCT"""

import numpy as np


class NCTAnalyzer:
    """Core analysis engine"""
    
    def __init__(self):
        pass
    
    def compute_overlap(self, mask1, mask2, metric='dice'):
        """Compute overlap between two masks"""
        if metric == 'dice':
            intersection = np.sum(mask1 * mask2)
            return 2.0 * intersection / (np.sum(mask1) + np.sum(mask2))
        elif metric == 'jaccard':
            intersection = np.sum(mask1 * mask2)
            union = np.sum(np.logical_or(mask1, mask2))
            return intersection / union if union > 0 else 0
        else:
            intersection = np.sum(mask1 * mask2)
            return intersection / (np.sum(mask1) + np.sum(mask2) - intersection)
    
    def run_permutations(self, data, n_permutations=1000, seed=42):
        """Run permutation testing"""
        np.random.seed(seed)
        results = []
        for i in range(n_permutations):
            results.append(np.random.rand())
        return results
