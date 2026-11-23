# Архитектура JANUS v20.3-scientific

Этот документ описывает динамическую карту влияния параметров, метрик и гипотез в эволюционном фреймворке JANUS. Все элементы соответствуют слоям мета-реестра.

## Диаграмма потоков

```mermaid
flowchart TB
    subgraph L1 [layer_1_facts: Твёрдые факты]
        direction TB
        P1["gain (0.3–2.5)"]
        P2["temperature (0.3–2.0)"]
        P3["lr (1e-4–1e-2)"]
        P4["n_embd (32–128)"]
        P5["n_head (2–8)"]
        P6["n_layer (1–4)"]
        P7["hidden_states (2–10)"]
        P8["intra_cluster_prob (0.3–0.95)"]
        P9["switch_prob (0.05–0.5)"]
        P10["batch_size (128)"]
    end

    subgraph L2 [layer_2_observations: Метрики и феномены]
        M1["val_loss (базовый шум 6.907)"]
        M2["MI_unbiased (0.0 → ...)"]
        M3["Diversity (1.0 → ...)"]
        M4["Gap (train_loss - val_loss)"]
        M5["Dead Zone (val_loss ~6.9)"]
        M6["Reward Hacking Exploit"]
        M7["Mode Collapse"]
        M8["Curriculum Collapse"]
    end

    subgraph L4 [layer_4_speculation: Гипотезы и Next Steps]
        direction TB
        H1["HYP_TRUE_BASELINE (CONFIRMED)<br>val_loss < 6.907 → обучение"]
        H2["HYP_SENSITIVITY_DRIVEN (TESTING)<br>направленные мутации эффективнее Random Search"]
        H3["HYP_TOPOLOGICAL_RESONANCE (PROPOSED)<br>резонансные комбинации (n_embd, n_head, n_layer)"]
        H4["HYP_COEVOLUTIONARY_STABILITY (TESTING)<br>скользящее среднее защищает от сброса среды"]
        H5["HYP_PCIE_BOTTLENECK (VERIFIED_V6.3)<br>Zero-Transfer I/O ускорит выход из Dead Zone"]
        NEXT["Следующие шаги<br>Zero-Transfer, Attention Maps, Cosine Annealing"]
    end

    P1 & P2 -->|регулируют энтропию| M3
    P1 & P2 -->|при экстремальных значениях| M6
    P3 -->|скорость сходимости| M1
    P4 & P5 & P6 -->|ёмкость модели| M2
    P7 & P8 & P9 -->|сложность среды| M1 & M2
    P10 -->|стабильность градиентов| M1 & M4
    M5 -->|преодоление| H1
    H1 -->|подтверждено| M1
    H2 -.->|проверяется в v6.2.3| M2
    H3 -.->|потенциально влияет| P4 & P5 & P6
    H4 -.->|связана с| M8
    H5 -.->|реализуется в| NEXT
    M6 & M7 & M8 -.->|требуют решений из| NEXT