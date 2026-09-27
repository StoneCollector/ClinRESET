# ClinRESET Web Application

ClinRESET provides a FastAPI backend and a responsive, vanilla HTML/CSS/JavaScript frontend to analyze medical PDFs, classify report types, extract clinical findings and measurements, evaluate reported reference intervals, and display color-coded visual reports in the browser.

## Running the Web Application

1. **Activate the Virtual Environment**:
   ```powershell
   venv\Scripts\activate
   ```

2. **Start the FastAPI Server**:
   ```bash
   uvicorn web.app:app --reload
   ```

3. **Open the Application**:
   Navigate to [http://localhost:8000](http://localhost:8000) in your web browser.

## Architecture

- **Backend (`web/app.py`)**:
  - `POST /api/reports`: Receives multipart PDF upload, starts background extraction and report building, immediately returns `202 Accepted` with a `job_id`.
  - `GET /api/reports/{job_id}`: Polled by the frontend to monitor status (`processing`, `failed`, or `done`) and retrieve the rendered `FinalReport`.
  - `GET /api/health`: Health-check endpoint.
  - `GET /`: Serves the static frontend application.
- **Frontend (`web/static/`)**:
  - `index.html`: Semantic single-page application structure.
  - `style.css`: Clean, modern clinical aesthetic with custom alert color tokens and responsive grid layouts.
  - `app.js`: Drag-and-drop file upload, cosmetic progress feedback, status polling, and dynamic SVG range-bar chart rendering.
