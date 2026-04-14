# Adaptive Kalman + AMPC Greenhouse

> A smart greenhouse prototype oriented around Adaptive Kalman estimation and AMPC, starting from an offline ARX prediction baseline and report-ready estimation workflow.

---

## Overview

This project is a smart greenhouse system focused in v1 on reliable state estimation and AMPC-ready modeling, not immediate full autonomous control. It uses real or replayed greenhouse measurements to run a pipeline from data input through preprocessing, prediction, Adaptive Kalman-ready update, storage, visualization, and evaluation.

The initial development dataset is `../ARX/greenhouse_data.csv`, which includes timestamped soil moisture, temperature, humidity, light, setpoint, and actuator fields. The v1 goal is to prove that the prediction plus Adaptive Kalman-ready estimation path produces smoother, more useful estimates than raw sensor values alone, while keeping the architecture ready for AMPC state, cost, constraints, and safety logic.

The primary user is the project owner. The project exists because manual greenhouse observation and simple threshold actions are reactive, inconsistent, and weak at handling coupled environmental variables.

---

## Tech Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Frontend | Vite | Dashboard and visualization shell |
| Styling | CSS / Vite frontend styles | Exact UI system is TBD |
| Backend | Python / Django | Backend framework is assumed from Django ORM selection |
| Database | MySQL from XAMPP | Local relational storage for experiments and logs |
| ORM | Django ORM | Query layer for persisted experiment data |
| Auth | TBD | v1 must restrict configuration changes to authorized users |
| Hosting | AWS | Exact AWS service choice is TBD |
| CI/CD | TBD | Not required for first local prototype |

---

## Getting Started

### Prerequisites

- Node.js latest, not pinned yet
- npm
- Python with the dependencies from `../ARX/requirements.txt`
- XAMPP with MySQL enabled
- Access to `../ARX/greenhouse_data.csv`

### Installation

```bash
npm install
```

Install Python dependencies for the existing ARX work:

```bash
pip install -r ../ARX/requirements.txt
```

### Running Locally

```bash
npm run dev
```

### Running Tests

```bash
npm test
```

### Building

```bash
npm run build
```

### Starting

```bash
npm start
```

---

## Project Structure

```text
../ARX/
  greenhouse_data.csv       # Initial offline greenhouse dataset
  arx_pipeline.py           # Existing ARX model pipeline
./                          # Kalman project root
docs/
  technical/                # Architecture, API, database, decisions, design system
  content/                  # Future public-facing content strategy
  user/                     # User-facing workflow docs
.tasks/                     # Detailed task files
CLAUDE.md                   # Agent instructions
PRD.md                      # Product requirements
README.md                   # Project overview
TODO.md                     # Project backlog
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | MySQL connection string for Django ORM |
| `DJANGO_SECRET_KEY` | Yes | Django application secret |
| `DJANGO_DEBUG` | Yes | Local debug flag |
| `DJANGO_ALLOWED_HOSTS` | Yes | Allowed hostnames for Django deployment |
| `AWS_REGION` | TBD | AWS region if deployed to AWS |
| `AWS_ACCESS_KEY_ID` | TBD | AWS access key if direct AWS credentials are used |
| `AWS_SECRET_ACCESS_KEY` | TBD | AWS secret key if direct AWS credentials are used |

No secret values should be committed.

---

## Deployment

The deployment target is AWS, but the exact service choice is still open. v1 should remain practical to run locally on Windows with XAMPP MySQL and deployable to Linux when the AWS target is chosen.

---

## License

TBD.
