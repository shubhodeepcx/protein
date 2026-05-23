# SDLC.md

# Software Development Life Cycle Plan

**Project:** AI-Powered Protein Structure Visualization and Annotation Platform  
**Planned Duration:** 6 months  
**Document Type:** SDLC and Project Execution Plan  
**Version:** 1.0  
**Date:** 23 May 2026  

---

## 1. SDLC Model Selection

The recommended development model for this project is an **Agile Iterative SDLC with Prototype-Driven Development**.

This model is appropriate because:

- The project contains multiple research-heavy modules.
- Molecular visualization requires early prototyping.
- External APIs may behave differently during implementation.
- AI annotation quality needs repeated testing.
- User interface quality is very important.
- The project must remain flexible while still meeting a six-month deadline.

The project will be divided into monthly milestones and two-week sprints. Each sprint will produce a usable increment.

---

## 2. SDLC Phases

## 2.1 Phase 1: Requirement Analysis

Duration: Weeks 1–2

Activities:

- Define project scope.
- Identify users and use cases.
- Select core and stretch features.
- Study AlphaFold DB, RCSB PDB, UniProt, InterPro, PDBe-KB, DSSP, Foldseek, Mol*, and related tools.
- Define file upload requirements.
- Define viewer requirements.
- Define dashboard metrics.
- Define AI annotation boundaries.
- Identify unrealistic features and downscope them.

Deliverables:

- Product specification.
- Initial feature list.
- Feasibility matrix.
- Risk register.
- Technology stack decision.

Exit Criteria:

- Finalized MVP scope.
- Clear list of excluded/stretch features.
- Approved architecture direction.

---

## 2.2 Phase 2: System Design

Duration: Weeks 3–4

Activities:

- Design high-level architecture.
- Design database schema.
- Design API endpoints.
- Design frontend wireframes.
- Design backend modules.
- Design file storage strategy.
- Design background job system.
- Design AI annotation pipeline.
- Design security and validation workflows.

Deliverables:

- Architecture diagram.
- Database schema.
- API contract.
- UI wireframes.
- Module breakdown.
- Test strategy.

Exit Criteria:

- Development-ready design.
- Clear interface between frontend, backend, workers, and external APIs.

---

## 2.3 Phase 3: Prototype Development

Duration: Weeks 5–8

Activities:

- Build initial frontend layout.
- Integrate Mol* viewer.
- Implement file upload prototype.
- Parse basic PDB/mmCIF metadata.
- Display uploaded protein in 3D.
- Build simple dashboard.
- Implement basic residue click event.

Deliverables:

- Working 3D viewer prototype.
- Upload prototype.
- Basic protein metadata parser.
- Demo with 2–3 sample proteins.

Exit Criteria:

- User can upload a structure and view it in 3D.
- Basic metadata appears correctly.

---

## 2.4 Phase 4: Core System Development

Duration: Weeks 9–16

Activities:

- Build production-grade upload service.
- Implement user projects and saved proteins.
- Build chain/residue/atom parser.
- Implement residue highlighting.
- Implement sequence-to-structure linked viewer.
- Implement molecular analytics.
- Implement charts and dashboard.
- Add secondary structure assignment.
- Add RCSB, AlphaFold, and UniProt import.
- Add PDF/PNG export foundation.

Deliverables:

- Core web application.
- Upload and import system.
- Protein viewer.
- Analytics dashboard.
- Secondary structure view.
- Export MVP.

Exit Criteria:

- The system can analyze both uploaded and imported structures.
- Dashboard metrics are correct for test proteins.
- Users can generate screenshots and basic reports.

---

## 2.5 Phase 5: AI and Advanced Analysis Development

Duration: Weeks 17–21

Activities:

- Build AI annotation assistant.
- Add source-grounded context retrieval.
- Add InterPro/PDBe-KB annotation import where available.
- Add AlphaFold confidence analysis.
- Add mutation impact visualizer.
- Add comparative protein view.
- Add contact map or similarity search depending on time.

Deliverables:

- AI assistant.
- Mutation analysis module.
- Comparative view.
- Confidence analysis.
- Advanced report sections.

Exit Criteria:

- AI assistant produces useful, source-aware summaries.
- Mutation visualizer works for simple mutations.
- Comparative structure workflow works for selected examples.

---

## 2.6 Phase 6: Testing, Optimization, and Deployment

Duration: Weeks 22–24

Activities:

- Perform unit testing.
- Perform integration testing.
- Perform UI testing.
- Validate scientific calculations.
- Test with real PDB/mmCIF files.
- Test external API failure cases.
- Optimize viewer performance.
- Harden upload security.
- Deploy application.
- Prepare demo dataset.
- Prepare final report and presentation.

Deliverables:

- Deployed application.
- Final project report.
- User manual.
- Test report.
- Demo video or walkthrough.

Exit Criteria:

- Application is stable enough for demonstration.
- Core features pass acceptance tests.
- Final documentation is complete.

---

## 3. Six-Month Roadmap

| Month | Focus | Major Deliverables |
|---|---|---|
| Month 1 | Research + Design | Requirement analysis, architecture, UI design, API design |
| Month 2 | Viewer + Upload Prototype | Mol* integration, upload parser, basic dashboard |
| Month 3 | Core Analytics + Database Import | RCSB/AlphaFold/UniProt integration, residue/chain analytics |
| Month 4 | Secondary Structure + Export + AI Base | DSSP/secondary structure, PDF/PNG export, AI assistant MVP |
| Month 5 | Advanced Features | Mutation visualizer, comparative view, confidence analysis, contact map |
| Month 6 | Testing + Polish + Deployment | Final UI, reports, test cases, deployment, final documentation |

---

## 4. Sprint Plan

Each sprint is approximately 2 weeks.

## Sprint 1: Requirement and Feasibility

Goals:

- Freeze MVP scope.
- Define data sources.
- Identify excluded features.
- Prepare architecture draft.

Tasks:

- Study protein data formats.
- Study Mol* integration.
- Study RCSB/AlphaFold/UniProt APIs.
- Create feature priority list.
- Create risk matrix.

Output:

- Feature backlog.
- Final MVP list.
- Initial technical stack.

---

## Sprint 2: Architecture and UI Design

Goals:

- Finalize system design.
- Create database schema.
- Create UI wireframes.

Tasks:

- Design backend services.
- Design data model.
- Design API contract.
- Design dashboard layout.
- Design viewer layout.

Output:

- Architecture design.
- UI mockups.
- API specification.

---

## Sprint 3: Viewer Prototype

Goals:

- Embed Mol* viewer.
- Load sample protein file.

Tasks:

- Set up frontend project.
- Create viewer page.
- Load static PDB/mmCIF file.
- Add camera controls.
- Add visualization mode selector.

Output:

- Working protein viewer page.

---

## Sprint 4: Upload and Parser Prototype

Goals:

- Upload file and parse basic structure data.

Tasks:

- Build upload API.
- Validate file type.
- Parse chains/residues/atoms.
- Store uploaded file.
- Display uploaded protein.

Output:

- Upload-to-viewer workflow.

---

## Sprint 5: Dashboard Analytics

Goals:

- Generate protein statistics.

Tasks:

- Calculate molecular weight.
- Calculate residue composition.
- Calculate chain statistics.
- Create analytics API.
- Build dashboard charts.

Output:

- Protein dashboard.

---

## Sprint 6: Residue and Sequence Interaction

Goals:

- Build residue-level exploration.

Tasks:

- Add residue click event.
- Build sequence panel.
- Sync sequence and 3D selection.
- Highlight amino acid classes.
- Add residue search.

Output:

- Interactive residue explorer.

---

## Sprint 7: Public Database Integration

Goals:

- Import from biological databases.

Tasks:

- Add RCSB search/import.
- Add AlphaFold import.
- Add UniProt metadata import.
- Cache imported results.
- Show source badges.

Output:

- Search and import workflow.

---

## Sprint 8: Secondary Structure and Confidence

Goals:

- Add secondary structure and AlphaFold confidence analysis.

Tasks:

- Integrate DSSP or fallback secondary structure parser.
- Add secondary structure coloring.
- Add secondary structure charts.
- Add pLDDT coloring for AlphaFold models.
- Add confidence histogram.

Output:

- Secondary structure and confidence-aware viewer.

---

## Sprint 9: AI Annotation Assistant

Goals:

- Add AI-powered explanations.

Tasks:

- Create annotation context builder.
- Add AI prompt templates.
- Add protein summary mode.
- Add selected residue explanation mode.
- Add source list to AI output.

Output:

- AI assistant MVP.

---

## Sprint 10: Mutation and Comparison

Goals:

- Add advanced biological interpretation features.

Tasks:

- Build mutation notation parser.
- Add amino acid property comparison.
- Highlight mutation in 3D.
- Add nearby residue detection.
- Create comparative protein page.
- Calculate simple RMSD/alignment where feasible.

Output:

- Mutation visualizer and basic comparison view.

---

## Sprint 11: Export and Reporting

Goals:

- Produce professional exports.

Tasks:

- Add viewer screenshot export.
- Add PNG export.
- Add PDF report generator.
- Add JSON/CSV exports.
- Add report preview page.

Output:

- Export system.

---

## Sprint 12: Testing, Deployment, and Final Polish

Goals:

- Stabilize and deploy the system.

Tasks:

- Write unit tests.
- Test real proteins.
- Fix UI bugs.
- Add error states.
- Deploy frontend and backend.
- Prepare demo proteins.
- Prepare final documentation.

Output:

- Final deployable project.

---

## 5. Team Roles

For a small student team, roles can overlap.

| Role | Responsibility |
|---|---|
| Project Lead | Scope, planning, integration, final demo |
| Frontend Developer | UI, viewer, dashboard, sequence panel |
| Backend Developer | APIs, upload, database, jobs, exports |
| Bioinformatics Developer | structure parsing, analytics, DSSP/Foldseek integration |
| AI/ML Developer | AI assistant, mutation explanation, RAG pipeline |
| QA/Documentation Lead | testing, report, user manual, screenshots |

For solo development, the work should be prioritized as:

1. Viewer.
2. Upload.
3. Analytics.
4. Database import.
5. AI assistant.
6. Mutation/comparison.
7. Export/report.
8. Stretch features.

---

## 6. Backlog Prioritization

## 6.1 Must Have

- Protein 3D viewer.
- PDB/mmCIF upload.
- Structure parser.
- Residue highlighting.
- Sequence panel.
- Dashboard analytics.
- Secondary structure.
- AlphaFold/RCSB/UniProt import.
- PDF/PNG export.

## 6.2 Should Have

- AI annotation assistant.
- AlphaFold confidence coloring.
- Mutation impact visualizer.
- Comparative view.
- Contact map.

## 6.3 Could Have

- Foldseek similarity search.
- PDBe-KB advanced annotations.
- InterPro domain API integration.
- Shareable reports.
- Public protein gallery.

## 6.4 Won't Have in Initial Release

- Full AlphaFold reproduction.
- Training huge protein transformers.
- Real-time universal folding.
- Production-grade molecular dynamics.
- Pharma-grade docking engine.

---

## 7. Development Standards

### 7.1 Code Standards

- Use TypeScript for frontend.
- Use Python type hints for backend.
- Follow modular folder structure.
- Use clear service boundaries.
- Use environment variables for secrets.
- Avoid hardcoded API keys.
- Add meaningful logs.

### 7.2 Git Workflow

Recommended branches:

- `main`: stable production branch.
- `dev`: integration branch.
- `feature/viewer`.
- `feature/upload-parser`.
- `feature/dashboard`.
- `feature/ai-assistant`.
- `feature/mutation-visualizer`.
- `feature/report-export`.

Pull request checklist:

- Feature works locally.
- Tests pass.
- No secrets committed.
- API changes documented.
- UI screenshots attached for frontend changes.

---

## 8. Testing Strategy

## 8.1 Unit Testing

Test:

- Amino acid conversion.
- Molecular weight calculation.
- Residue composition calculation.
- Chain parser.
- Mutation notation parser.
- Hydrophobicity calculation.
- API request validators.

Tools:

- Pytest for backend.
- Vitest/Jest for frontend.

---

## 8.2 Integration Testing

Test:

- Upload → parse → save → view.
- Search → import → analyze.
- Protein → AI annotation.
- Protein → PDF export.
- Mutation input → highlight → report.

---

## 8.3 UI Testing

Test:

- Viewer loads.
- Dashboard renders.
- Sequence panel scrolls.
- Residue click works.
- Export buttons work.
- Error states appear correctly.

Tools:

- Playwright or Cypress.

---

## 8.4 Scientific Validation Testing

Use known proteins:

- Insulin.
- Hemoglobin.
- Green fluorescent protein.
- Lysozyme.
- p53 DNA-binding domain.
- SARS-CoV-2 spike protein fragment.

Validate:

- Chain count.
- Residue count.
- Molecular weight approximate correctness.
- Secondary structure percentage reasonableness.
- Viewer correctness.
- Metadata retrieval correctness.

---

## 8.5 Security Testing

Test:

- Invalid file upload.
- Huge file upload.
- Path traversal filename.
- Wrong extension.
- API rate limit.
- Unauthorized project access.
- Report download permission.

---

## 9. Deployment Plan

## 9.1 Environments

| Environment | Purpose |
|---|---|
| Local | Development |
| Staging | Testing and demo rehearsal |
| Production | Final deployed version |

## 9.2 Recommended Deployment

Frontend:

- Vercel, Netlify, or container deployment.

Backend:

- Railway, Render, Fly.io, VPS, or cloud VM.

Database:

- PostgreSQL managed database.

Storage:

- S3-compatible object storage or local storage for demo.

Worker:

- Separate background worker process.

## 9.3 Environment Variables

Examples:

```bash
DATABASE_URL=
REDIS_URL=
OBJECT_STORAGE_ENDPOINT=
OBJECT_STORAGE_ACCESS_KEY=
OBJECT_STORAGE_SECRET_KEY=
AI_PROVIDER_API_KEY=
JWT_SECRET=
MAX_UPLOAD_SIZE_MB=50
```

---

## 10. Risk Register

| ID | Risk | Probability | Impact | Mitigation |
|---|---|---:|---:|---|
| R1 | Mol* integration complexity | Medium | Medium | Prototype early |
| R2 | Uploaded PDB files inconsistent | High | High | Strong parser validation |
| R3 | AI hallucination | Medium | High | Use RAG and source grounding |
| R4 | External APIs unavailable | Medium | Medium | Cache and fallback states |
| R5 | MD/docking scope creep | High | High | Mark as stretch only |
| R6 | Time shortage | High | High | Finish MVP first |
| R7 | Scientific calculation errors | Medium | High | Validate against known proteins |
| R8 | Large files slow UI | Medium | Medium | Size limits and async processing |
| R9 | Report generation bugs | Medium | Medium | Build export early, polish later |
| R10 | Deployment issues | Medium | Medium | Deploy staging by Month 4 |

---

## 11. Quality Metrics

| Metric | Target |
|---|---:|
| Viewer load success for test proteins | 95%+ |
| Upload parser success for valid files | 90%+ |
| Dashboard generation time for medium proteins | < 5 seconds |
| API response time for cached records | < 1 second |
| PDF generation time | < 15 seconds |
| Critical security bugs | 0 |
| Core feature completion | 100% |
| Advanced feature completion | 60–80% |

---

## 12. Definition of Done

A feature is considered done when:

1. It works locally.
2. It works on staging.
3. It handles errors gracefully.
4. It has at least basic tests.
5. It is documented.
6. It does not break existing workflows.
7. It has clear UI feedback.
8. It is included in the demo checklist if user-facing.

---

## 13. Final Deliverables

By the end of the six-month SDLC, the project should deliver:

1. Deployed web application.
2. Source code repository.
3. Product specification.
4. SDLC document.
5. Project report.
6. User manual.
7. Test report.
8. Demo dataset.
9. Demo video or presentation.
10. Final PDF sample report generated by the system.

---

## 14. Maintenance Plan

Post-release activities:

- Fix bugs reported during demo.
- Add more database integrations.
- Improve AI assistant accuracy.
- Add more export templates.
- Improve performance for large proteins.
- Add user feedback system.
- Add optional docking/MD only after MVP is stable.

---

## 15. Final SDLC Recommendation

The project should be executed as a staged, prototype-first Agile project. The safest path is:

1. Build the viewer first.
2. Build upload and parser second.
3. Build analytics third.
4. Add database integrations fourth.
5. Add AI assistant fifth.
6. Add mutation/comparison sixth.
7. Add stretch features only after the core system is stable.

This avoids the common trap of spending months on impossible features such as AlphaFold reproduction, huge model training, full MD simulation, or drug docking before the actual product works.
