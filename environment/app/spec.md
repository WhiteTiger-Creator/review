# Technical Specification: `godeep-rl` (v2.0 Extreme Hard)

## Overview
`godeep-rl` is an enterprise-grade Machine Learning & Reinforcement Learning framework in pure Go under `/app`. It implements 4D dynamic tensor autograd computation graphs, Multi-Head Self-Attention with NTK-aware Rotary Position Embeddings (RoPE), per-head asymmetric INT8 quantized KV-caching, PPO actor-critic optimization with episodic GAE-$\lambda$, and distributed gradient ring-allreduce with norm clipping.

---

## Technical Requirements & Formulas

### 1. `tensor` & `ml/autograd.go` (4D Tensor & Dynamic Autograd)
- **Tensor Storage**: 4D shape `[Batch, Heads, SeqLen, Dim]`. Memory strides computed as $S_i = \prod_{j=i+1}^3 \text{Shape}[j]$.
- **4D MatMul**: Multiplies last two dimensions for each batch and head slice:
  $$\mathbf{C}_{b,h,m,n} = \sum_{k=0}^{K-1} \mathbf{A}_{b,h,m,k} \cdot \mathbf{B}_{b,h,k,n}$$
- **Topological Sorting & Backward Pass**:
  - `Tensor.Backward()` must perform post-order depth-first traversal of computation DAG nodes.
  - Multi-consumer nodes must accumulate gradients: $\mathbf{g}_{\text{target}} \leftarrow \mathbf{g}_{\text{target}} + \mathbf{g}_{\text{incoming}}$.
- **MatMul Gradients**:
  - $\nabla \mathbf{A}_{b,h,m,k} = \sum_{n=0}^{N-1} \nabla \mathbf{C}_{b,h,m,n} \cdot \mathbf{B}_{b,h,k,n}$
  - $\nabla \mathbf{B}_{b,h,k,n} = \sum_{m=0}^{M-1} \mathbf{A}_{b,h,m,k} \cdot \nabla \mathbf{C}_{b,h,m,n}$
- **Softmax Backward**:
  For Softmax output $\mathbf{Y}$: $(\nabla \mathbf{X})_i = \mathbf{Y}_i \left( (\nabla \mathbf{Y})_i - \sum_j (\nabla \mathbf{Y})_j \mathbf{Y}_j \right)$.

### 2. `ml/transformer.go` (NTK-Aware RoPE & Multi-Head Causal Attention)
- **NTK-Aware RoPE Scaling**:
  For position $m$ and dimension pair $(2i, 2i+1)$:
  $$\theta_i = (\alpha \cdot 10000)^{-2i/d} \quad \text{where } \alpha = 1.0$$
  $$R_{m,i} = \begin{pmatrix} \cos(m\theta_i) & -\sin(m\theta_i) \\ \sin(m\theta_i) & \cos(m\theta_i) \end{pmatrix}$$
  Rotates Query $\mathbf{Q}$ and Key $\mathbf{K}$ vectors.
- **Causal Masking**:
  Attention scores $\mathbf{S}_{i,j} = \frac{\mathbf{Q}_i \cdot \mathbf{K}_j^T}{\sqrt{d_k}}$.
  If $j > i$, set $\mathbf{S}_{i,j} = -10^9$ (representing $-\infty$) before Softmax.

### 3. `ml/kvcache.go` (Per-Head Asymmetric INT8 Quantization)
- **Per-Head Scale & Zero-Point**:
  For each head $h \in [0, H-1]$:
  $$\text{scale}_h = \frac{\max(\mathbf{X}_h) - \min(\mathbf{X}_h)}{255.0}$$
  $$\text{zero\_point}_h = \text{clamp}\left( \left\lfloor \frac{-\min(\mathbf{X}_h)}{\text{scale}_h} \right\rceil - 128, \, -128, \, 127 \right)$$
  $$q_{h,i} = \text{clamp}\left( \left\lfloor \frac{x_{h,i}}{\text{scale}_h} \right\rceil + \text{zero\_point}_h, \, -128, \, 127 \right)$$
- **Dequantization**:
  $$x_{h,i}^{\text{approx}} = (q_{h,i} - \text{zero\_point}_h) \times \text{scale}_h$$

### 4. `ml/ppo.go` (Episodic GAE-$\lambda$ & PPO Loss)
- **Episodic GAE-$\lambda$**:
  Given rewards $r_t$, values $V(s_t)$, and episode termination flags $d_t \in \{0, 1\}$:
  $$\delta_t^V = r_t + \gamma (1 - d_t) V(s_{t+1}) - V(s_t)$$
  $$\hat{A}_t = \delta_t^V + \gamma \lambda (1 - d_t) \hat{A}_{t+1}$$
  (Computed backward from $t = T-1$ to $0$).
- **Advantage Normalization**:
  $$\hat{A}_t \leftarrow \frac{\hat{A}_t - \mu_A}{\sigma_A + 10^{-8}}$$
- **PPO Clipped Surrogate Loss**:
  $$r_t(\theta) = \frac{\pi_\theta(a_t | s_t)}{\pi_{\theta_{\text{old}}}(a_t | s_t)}$$
  $$L^{\text{CLIP}}(\theta) = -\frac{1}{T} \sum_{t=0}^{T-1} \min\left( r_t(\theta) \hat{A}_t, \, \text{clip}(r_t(\theta), 1-\epsilon, 1+\epsilon) \hat{A}_t \right)$$

### 5. `ml/distributed.go` (Gradient Norm Clipping & Ring-AllReduce)
- **Global Gradient $L_2$ Norm Clipping**:
  $$\|\mathbf{g}\|_2 = \sqrt{ \sum_{p} \sum_{i} g_{p,i}^2 }$$
  If $\|\mathbf{g}\|_2 > g_{\max}$:
  $$\mathbf{g}_p \leftarrow \mathbf{g}_p \times \frac{g_{\max}}{\|\mathbf{g}\|_2 + 10^{-6}}$$

---

## CLI Specifications
- `godeep-rl train`: Executes 50 training iterations. Output must confirm final loss $< 0.4$.
- `godeep-rl eval`: Evaluates policy across 10 evaluation episodes. Output average reward.
- `godeep-rl quantize-kv`: Executes INT8 per-head quantization benchmark and reports MAE $< 0.03$.
