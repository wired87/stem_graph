"""
SemanticMaster: embeds graph nodes, adds 24 data-science technique nodes,
and creates semantic similarity edges with rel varying per technique.
"""
import sys
from typing import Any, Dict, List


DATA_PROCESSORS: List[Dict[str, Any]] = [
    {"name": "GradientDescent", "equation": "theta_{j+1} = theta_j - alpha * gradient(J(theta_j))",
     "python_library": ["torch.optim.SGD", "jax.example_libraries.optimizers", "scipy.optimize.minimize"]},
    {"name": "NormalDistribution", "equation": "f(x|mu,sigma^2) = (1/(sigma*sqrt(2*pi))) * exp(-(x-mu)^2/(2*sigma^2))",
     "python_library": ["scipy.stats.norm", "numpy.random.normal", "torch.distributions.Normal"]},
    {"name": "ZScore", "equation": "z = (x - mu) / sigma",
     "python_library": ["scipy.stats.zscore", "sklearn.preprocessing.StandardScaler"]},
    {"name": "Sigmoid", "equation": "sigma(x) = 1/(1 + exp(-x))",
     "python_library": ["torch.nn.Sigmoid", "scipy.special.expit", "jax.nn.sigmoid"]},
    {"name": "Correlation", "equation": "corr(X,Y) = Cov(X,Y)/(Std(X)*Std(Y))",
     "python_library": ["numpy.corrcoef", "scipy.stats.pearsonr", "pandas.DataFrame.corr"]},
    {"name": "CosineSimilarity", "equation": "similarity(A,B) = (A·B)/(||A||*||B||)",
     "python_library": ["sklearn.metrics.pairwise.cosine_similarity", "scipy.spatial.distance.cosine", "torch.nn.functional.cosine_similarity"]},
    {"name": "NaiveBayes", "equation": "P(y|x1..xn) = P(y)*Π P(xi|y) / P(x1..xn)",
     "python_library": ["sklearn.naive_bayes.GaussianNB", "sklearn.naive_bayes.MultinomialNB"]},
    {"name": "MaximumLikelihoodEstimation", "equation": "argmax(theta) Π P(x_i | theta)",
     "python_library": ["scipy.optimize", "statsmodels"]},
    {"name": "OrdinaryLeastSquares", "equation": "beta = (X^T X)^(-1) X^T y",
     "python_library": ["sklearn.linear_model.LinearRegression", "statsmodels.api.OLS", "numpy.linalg.lstsq"]},
    {"name": "F1Score", "equation": "F1 = (2*Precision*Recall)/(Precision+Recall)",
     "python_library": ["sklearn.metrics.f1_score"]},
    {"name": "ReLU", "equation": "ReLU(x) = max(0,x)",
     "python_library": ["torch.nn.ReLU", "jax.nn.relu", "tensorflow.nn.relu"]},
    {"name": "EigenVectors", "equation": "A v = lambda v",
     "python_library": ["numpy.linalg.eig", "scipy.linalg.eig"]},
    {"name": "R2Score", "equation": "R^2 = 1 - Σ(yi-y_hat)^2 / Σ(yi-y_bar)^2",
     "python_library": ["sklearn.metrics.r2_score"]},
    {"name": "Softmax", "equation": "softmax(x_i) = exp(x_i) / Σ exp(x_j)",
     "python_library": ["torch.nn.Softmax", "jax.nn.softmax", "scipy.special.softmax"]},
    {"name": "MeanSquaredError", "equation": "MSE = (1/n) Σ(yi - y_hat)^2",
     "python_library": ["sklearn.metrics.mean_squared_error", "torch.nn.MSELoss"]},
    {"name": "RidgeRegression", "equation": "MSE + lambda Σ(beta_j^2)",
     "python_library": ["sklearn.linear_model.Ridge"]},
    {"name": "Entropy", "equation": "H(P) = - Σ P(x) log P(x)",
     "python_library": ["scipy.stats.entropy"]},
    {"name": "KLDivergence", "equation": "D_KL(P||Q) = Σ P(x) log(P(x)/Q(x))",
     "python_library": ["scipy.stats.entropy", "torch.nn.functional.kl_div"]},
    {"name": "LogLoss", "equation": "LogLoss = -(1/N) Σ [y log(p) + (1-y) log(1-p)]",
     "python_library": ["sklearn.metrics.log_loss", "torch.nn.BCELoss"]},
    {"name": "SVD", "equation": "A = U Σ V^T",
     "python_library": ["numpy.linalg.svd", "scipy.linalg.svd", "torch.linalg.svd"]},
    {"name": "LagrangeMultiplier", "equation": "L(x,λ) = f(x) - λ g(x)",
     "python_library": ["scipy.optimize.minimize(method='SLSQP')"]},
    {"name": "SVM", "equation": "min(w,b) 1/2||w||^2 + C Σ max(0,1 - y_i(w·x_i - b))",
     "python_library": ["sklearn.svm.SVC", "sklearn.svm.LinearSVC"]},
    {"name": "LinearRegression", "equation": "y = beta0 + beta1 x1 + ... + beta_n x_n + epsilon",
     "python_library": ["sklearn.linear_model.LinearRegression"]},
    {"name": "PCA", "equation": "X_reduced = X @ V_k where V from SVD",
     "python_library": ["sklearn.decomposition.PCA", "numpy.linalg.svd"]},
]


class SemanticMaster:
    """
    Receives GUtils instance. Embeds all nodes, adds technique nodes,
    and creates semantic similarity edges with rel varying per technique.
    """

    def __init__(self, g_utils: Any):
        self.g = g_utils

    def _node_to_text(self, nid: str, attrs: Dict[str, Any]) -> str:
        """Build text for embedding from node id, type, docstring, etc."""
        parts = [str(nid), str(attrs.get("type", "")), str(attrs.get("name", ""))]
        if attrs.get("docstring"):
            parts.append(str(attrs["docstring"])[:500])
        if attrs.get("equation"):
            parts.append(str(attrs["equation"]))
        if attrs.get("code"):
            parts.append(str(attrs["code"])[:300])
        return " ".join(p for p in parts if p).strip() or f"{nid} {attrs.get('type','')}"

    def add_technique_nodes(self) -> None:
        """Add 24 data-science technique nodes to the graph."""
        for proc in DATA_PROCESSORS:
            name = proc["name"]
            self.g.add_node(attrs=dict(
                id=name,
                type="TECHNIQUE",
                name=name,
                equation=proc.get("equation", ""),
                python_library=proc.get("python_library", []),
            ))
            print(f"TECHNIQUE node added: {name}", file=sys.stderr)

    def embed_all_nodes(self) -> Dict[str, Any]:
        """Embed all graph nodes; return dict nid -> vector (as tuple for similarity)."""
        from embedder import embed, similarity

        embeddings = {}
        for nid, attrs in self.g.G.nodes(data=True):
            text = self._node_to_text(nid, attrs)
            vec = embed(text)
            embeddings[nid] = tuple(vec.tolist())
        print(f"Embedded {len(embeddings)} nodes", file=sys.stderr)
        return embeddings

    def add_similarity_edges(self, threshold: float = 0.5) -> None:
        """
        Add semantic similarity edges. Node-to-node: rel=CosineSimilarity.
        Node-to-technique: rel=technique_name.
        """
        from embedder import similarity

        embs = self.embed_all_nodes()
        if not embs:
            return
        nids = list(embs.keys())
        technique_ids = {p["name"] for p in DATA_PROCESSORS}

        for i, nid_a in enumerate(nids):
            for nid_b in nids[i + 1:]:
                if nid_a == nid_b:
                    continue
                score = similarity(embs[nid_a], embs[nid_b])
                if score >= threshold:
                    self.g.add_edge(
                        src=nid_a,
                        trgt=nid_b,
                        attrs=dict(
                            rel="CosineSimilarity",
                            src_layer="NODE",
                            trgt_layer="NODE",
                            score=round(float(score), 4),
                        ),
                    )
                    print(f"LINK CosineSimilarity: {nid_a} -> {nid_b} score={score:.4f}", file=sys.stderr)

        # Node-to-technique: rel=technique_name
        for nid in nids:
            if nid in technique_ids:
                continue
            for tech_id in technique_ids:
                if tech_id not in embs:
                    continue
                score = similarity(embs[nid], embs[tech_id])
                if score >= threshold:
                    self.g.add_edge(
                        src=nid,
                        trgt=tech_id,
                        attrs=dict(
                            rel=tech_id,
                            src_layer="NODE",
                            trgt_layer="TECHNIQUE",
                            score=round(float(score), 4),
                        ),
                    )
                    print(f"LINK {tech_id}: {nid} -> {tech_id} score={score:.4f}", file=sys.stderr)

    def run(self, threshold: float = 0.5) -> None:
        """Orchestrate: add technique nodes -> embed -> add similarity edges."""
        self.add_technique_nodes()
        self.add_similarity_edges(threshold=threshold)
