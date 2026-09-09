# 🎯 Radar B2B: AI-Driven Lead Generation Pipeline

## 📌 Overview
Radar B2B is an end-to-end data engineering pipeline designed to transform raw, chaotic public government data (Brazilian CNPJ registry) into actionable, AI-enriched B2B sales opportunities. 

Unlike standard web scrapers, this project implements a robust **Medallion Architecture** focusing on Change Data Capture (CDC) to identify newly opened companies, match them against an Ideal Customer Profile (ICP), and generate ready-to-use sales scripts using LLMs.

## 🏗️ Architecture & Tech Stack
The pipeline is built with a strict "Zero-Cost MVP" philosophy, leveraging local out-of-core processing before scaling to the cloud.

*   **Orchestration:** Python
*   **Ingestion:** `httpx` (resilient chunked downloads from unstable government APIs)
*   **Storage & Compute:** DuckDB (Local Data Lake handling Parquet partitions)
*   **Transformation:** dbt-core (Bronze, Silver, and Gold layers)
*   **AI Enrichment:** Google Gemini API (Structured Outputs via Pydantic)
*   **CI/CD:** GitHub Actions

## ⚙️ How It Works (The Pipeline)
1. **Bronze Layer (Extract & Load):** Ingests raw `.zip` and `.csv` files, partitioning data by competence month directly into Parquet files.
2. **Silver Layer (Transform & CDC):** Cleanses data and applies a *Left Anti Join* strategy to compare the current month's snapshot against the previous one, reliably detecting `NEW_COMPANY` events.
3. **Gold Layer (Business Logic):** Filters events based on dynamic ICP rules (e.g., specific industries and regions) and calculates a deterministic Opportunity Score.
4. **LLM Enrichment:** Passes top-scored opportunities to an LLM to interpret the company's operational context, likely pain points, and generates a personalized sales pitch.
5. **Digest Generation:** Outputs a clean, actionable Markdown report for the sales team.

## 🚀 Getting Started
```bash
# Clone the repository
git clone [https://github.com/GabrielKSG7/radar-b2b.git](https://github.com/GabrielKSG7/radar-b2b.git)

# Install dependencies using uv
uv venv
uv pip install -r requirements.txt

# Run the end-to-end pipeline
python run_pipeline.py
