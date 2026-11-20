<div align="center">

# 🏠 CTRx: Central Tenancy Records

### A Centralized Rental Identity, Tenancy Management & Trust Platform

**Identity. History. Trust.**

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat-square&logo=sqlalchemy&logoColor=white)
![Alembic](https://img.shields.io/badge/Alembic-6BA81E?style=flat-square)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)

*Building trust, transparency, and accountability in the rental ecosystem through verifiable tenancy records and digital identity management.*

[**💻 Source Code**](https://github.com/AhsanCS64/CTRx) · [**👤 Developer Portfolio**](https://ahsanhabibkushal.vercel.app/)

</div>

> [!IMPORTANT]
> CTRx is an **independent software engineering project**. It is **not** an official government service, a government-authorized rental registry, or an officially recognized identity certification service.

---

## 📑 Table of Contents

- [Overview](#-overview)
- [The Problem](#-the-problem)
- [The Solution](#-the-solution)
- [Core Modules](#-core-modules)
- [Tech Stack](#-tech-stack)
- [Architecture](#-architecture)
- [Database Design](#-database-design)
- [Getting Started](#-getting-started)
- [Docker](#-docker)
- [Design Philosophy](#-design-philosophy)
- [Privacy, Security & Governance](#-privacy-security--governance)
- [Roadmap](#-roadmap)
- [Author](#-author)

---

## 🌍 Overview

**CTRx (Central Tenancy Records)** is a full-stack, database-driven platform for rental identity and tenancy management, built to address long-standing problems in residential renting, particularly in Bangladesh.

Rental arrangements often rely on informal agreements, scattered paperwork, and subjective judgments about tenants. That leaves landlords uncertain and puts tenants without an established rental history at a disadvantage. **Bachelors and students** are especially affected, since some property owners hesitate to rent to them because of perceived risk and a lack of reliable information.

CTRx explores a technology-driven answer: structured rental identities, verified tenancy histories, and transparent records that let documented behavior, rather than assumptions, guide rental decisions.

---

## ⚠️ The Problem

| Challenge | Impact |
|---|---|
| **Fragmented rental records** | Tenancy histories are rarely stored in one accessible place |
| **Limited tenant verification** | Owners have no standard way to evaluate prospective tenants |
| **Rental discrimination** | Students and bachelors face blanket assumptions |
| **No historical accountability** | Past tenancies and payment histories are hard to verify |
| **Informal documentation** | Agreements and records are inconsistent or poorly kept |
| **Opaque disputes** | Disagreements lack structured supporting evidence |

---

## 💡 The Solution

CTRx is built on three ideas:

| 🪪 Identity | 📜 History | 🤝 Trust |
|---|---|---|
| Verifiable rental identities for individuals and households | Structured, confirmed tenancy and payment records | Evidence-based reliability indicators that support human judgment |

Instead of treating every prospective tenant as an unknown, CTRx makes documented rental behavior available through privacy-conscious, accountable workflows. The long-term goal is for a tenant's demonstrated responsibility to count for more than stereotypes.

---

## 🧩 Core Modules

CTRx is organized into 12 functional domains.

| # | Module | Purpose |
|---|---|---|
| 1 | **Rental Identity Certificate (RIC)** | Standardized rental identity credential (details below) |
| 2 | **User & Account Management** | Centralized accounts for all participants in the rental ecosystem |
| 3 | **Tenant Management** | Tenant profiles, rental identities, and tenancy records |
| 4 | **Landlord Management** | Landlord information, property ownership links, and rental activity |
| 5 | **Property Management** | Rental properties and their ties to landlords and tenancies |
| 6 | **Tenancy Management** | Tenancy relationships between tenants, landlords, and properties |
| 7 | **Trust & Reliability** | Reliability assessment based on documented, verified history |
| 8 | **Rental Records** | Rental payments and other tenancy activity (details below) |
| 9 | **Dispute Management** | Structured recording and handling of disputes |
| 10 | **Government Administration** | Proposed structure for identity verification and governance |
| 11 | **Notification Management** | Communication about rental activity, requests, and account updates |
| 12 | **Audit Management** | Accountability logs for sensitive and administrative operations |

### 🪪 Rental Identity Certificate (RIC)

The RIC is the foundational concept of CTRx: a standardized rental identity for individuals or households on the platform. Proposed characteristics:

- Unique 12-digit, geography-coded identifier
- Household-based registration structure
- Identity verification and administrative approval
- Digital certificate generation in PDF format
- Optional linkage to previously issued rental identities
- Centralized certificate records

> The RIC is a **rental identity credential**, not a replacement for national identity documents.

### ⚖️ Trust & Reliability

The framework emphasizes verified rental records, timely payment histories, document verification, transparent reliability indicators, and safeguards against arbitrary assessments.

> Reliability indicators should **assist human judgment**, not automatically decide rental eligibility.

### 💳 Rental Records: Two-Party Payment Verification

```mermaid
flowchart TD
    A["Tenant initiates payment record"] --> B["Landlord reviews payment record"]
    B -->|Confirm| C["✅ Verified record"]
    B -->|Dispute| D["⚠️ Resolution workflow"]
```

Confirmed records are intended to be protected from unauthorized modification. Corrections go through accountable processes.

### 🏛 Government Administration

The concept includes local registration intake and centralized approval, subject to appropriate institutional authorization.

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python |
| **Backend framework** | FastAPI |
| **ASGI server** | Uvicorn |
| **Database** | PostgreSQL (via Psycopg) |
| **ORM** | SQLAlchemy |
| **Migrations** | Alembic |
| **Validation** | Pydantic |
| **Containerization** | Docker |
| **API style** | REST |
| **Version control** | Git & GitHub |

The stack favors maintainability, structured data modeling, and clear separation of responsibilities.

---

## 🏗 Architecture

CTRx uses a layered architecture that separates user interaction, business logic, and persistence.

```mermaid
flowchart TD
    U["🌐 Web Browser<br/>User Interface"] -- "HTTP / HTTPS" --> API["⚡ FastAPI Server<br/>Routing & Validation · Authentication · Business Logic"]
    API --> S["🧠 Service Layer<br/>Identity · Tenancy · Rental Records · Trust & Verification"]
    S --> O["🔗 SQLAlchemy ORM<br/>Models & Transactions"]
    O --> DB[("🐘 PostgreSQL<br/>Relational Records · Relationships · Persistence")]
    M["Alembic<br/>Schema Migrations"] -.-> DB
    D["Docker<br/>Containerized Runtime"] -.-> API
```

*This is the logical architecture. Deployment-specific organization may differ.*

---

## 🗄 Database Design

CTRx uses **PostgreSQL** to model closely connected entities:

- Users and identity credentials
- Tenants and landlords
- Properties and tenancy relationships
- Rental records and payment confirmations
- Trust-related information
- Disputes and administrative activities
- Notifications and audit records

The development schema contains approximately **30 tables**.

**Engineering principles**

- Relational integrity through primary and foreign keys
- Structured modeling of tenancy relationships
- Transaction-oriented operations
- Schema versioning with Alembic
- Separation of application logic from persistence
- Room for future schema evolution

---

## 🚀 Getting Started

### Repositories

| Repository | Description |
|---|---|
| [**CTRx**](https://github.com/AhsanCS64/CTRx) | Main application |
| **CTRx-Portable** | Dockerized distribution, maintained separately |

### Prerequisites

- Python 3.11 or later
- PostgreSQL, with database credentials
- Git

### 1. Clone the repository

```bash
git clone https://github.com/AhsanCS64/CTRx.git
cd CTRx
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
```

```powershell
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
```

```bash
# Linux / macOS
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the database

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/ctrx
```

> 🔒 Never commit real database passwords, connection secrets, or production `.env` files.

### 5. Run migrations

```bash
alembic upgrade head
```

### 6. Start the server

```bash
uvicorn main:app --reload
```

| URL | What you'll find |
|---|---|
| `http://127.0.0.1:8000` | The application |
| `http://127.0.0.1:8000/docs` | Interactive API docs (FastAPI Swagger UI) |

> These commands follow a conventional FastAPI setup. Check the repository for the actual entry point, dependency files, and environment variables before running.

---

## 🐳 Docker

The separate **CTRx-Portable** repository packages CTRx as a Docker distribution. Containerization provides:

- Reproducible execution environments
- Fewer differences between developer machines
- Easier distribution of dependencies
- Simpler setup on compatible systems
- Better isolation of application services

> Docker does not make an app publicly reachable by itself. Network configuration, database connectivity, and hosting determine whether it runs locally or over a network.

---

## 🧭 Design Philosophy

> **Rental opportunities should be influenced by verifiable responsibility, not generalized assumptions.**

CTRx aims to widen access for groups such as students and bachelors while respecting legitimate landlord concerns. The goal is **not** to remove landlord discretion, but to support better-informed and fairer decisions.

### Responsible trust assessment

A rental reliability framework has to be designed carefully. CTRx's trust model should prioritize:

- ✅ Explainable assessment criteria
- ✅ Verified information over unsubstantiated claims
- ✅ Privacy and data minimization
- ✅ Ways to dispute incorrect records
- ✅ Protection against discriminatory scoring
- ✅ Human review of consequential decisions

Trust indicators are not infallible measures of a person's character.

---

## 🔐 Privacy, Security & Governance

CTRx may process sensitive identity, residential, and financial information. A real-world deployment would require:

- Authentication and authorization
- Encryption and secure credential management
- Privacy and data retention policies
- Consent and lawful processing procedures
- Access logging and security monitoring
- Mechanisms for correcting inaccurate records
- Independent security testing
- Compliance with applicable laws and regulations

---

## 🗺 Roadmap

These are development goals, not claims that each capability exists today.

- [ ] Expand digital Rental Identity Certificate workflows
- [ ] More comprehensive tenancy verification
- [ ] Explainable, evidence-based reliability indicators
- [ ] Advanced dispute resolution workflows
- [ ] Stronger permission-based information access
- [ ] Tenant and landlord analytics
- [ ] Improved notification and administrative workflows
- [ ] Secure document verification
- [ ] Expanded auditability and record correction mechanisms
- [ ] Privacy-preserving identity interoperability
- [ ] Readiness for higher-volume deployment

---

## 👤 Author

**H. M. Ahsan Habib Kushal**
B.Sc. in Computer Science and Engineering, National Institute of Textile Engineering and Research (NITER), University of Dhaka

[![GitHub](https://img.shields.io/badge/GitHub-AhsanCS64-181717?style=flat-square&logo=github)](https://github.com/AhsanCS64)
[![Portfolio](https://img.shields.io/badge/Portfolio-ahsanhabibkushal-4CAF50?style=flat-square&logo=vercel&logoColor=white)](https://ahsanhabibkushal.vercel.app/)

---

<div align="center">

### CTRx: Identity. History. Trust.

*Modernizing residential rental management through structured information, responsible verification, and software engineering.*

</div>
