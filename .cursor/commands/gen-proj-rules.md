# Generate Project Rules

Create project-specific rules based on user requirements and project context.

## Instructions

### 1. Understand User Request
- Clarify what aspect of the project needs rules (domain, workflow, architecture, style)
- Ask for specific examples or scenarios if needed
- Identify the scope: single feature, domain area, or project-wide standards

### 2. Analyze Project Context
- Review key project files:
  - `README.md` - Project overview and goals
  - `TODOs.md` or similar - Current development plan
  - `package.json` or `pyproject.toml` - Tech stack and dependencies
  - Core source files in main directories (e.g., `src/`, `backend/`, `frontend/`)
- Identify:
  - Technology stack (frameworks, languages, tools)
  - Architecture patterns (MVC, microservices, monorepo, etc.)
  - Existing conventions (naming, file structure, testing)
  - Domain concepts and business logic

### 3. Create Rule Files
- Create `.cursor/rules/` directory if it doesn't exist
- Generate `.mdc` files with descriptive names
- **One file per domain/feature area** (e.g., `api-design.mdc`, `database-schema.mdc`, `frontend-components.mdc`)

### 4. Structure Each Rule File

```markdown
---
alwaysApply: true  # or false for optional rules
description: Brief description of what this rule covers
---

# [Rule Title]

## Overview
Brief explanation of the domain/feature and why these rules exist.

## Domain Knowledge
- Key concepts and terminology
- Business logic patterns
- Data models and relationships
- Common workflows

## Standards & Conventions
- Code structure and organization
- Naming conventions
- File/folder patterns
- Import/export patterns

## Implementation Patterns
- Common code patterns and templates
- Reusable components or utilities
- Error handling approaches
- Testing strategies

## Examples
```[language]
// Concrete code examples demonstrating the rules
```

## Checklist
- [ ] Key validation points
- [ ] Common pitfalls to avoid
- [ ] Required dependencies or setup

## References
- Links to relevant documentation
- Related rule files
```

### 5. Rule Categories

**Domain Knowledge Systematization**
- Business logic and domain models
- Data schemas and relationships
- API contracts and interfaces
- Key algorithms or calculations

**Workflow & Template Automation**
- Feature development workflow (e.g., "Adding a new API endpoint")
- Code generation templates
- Testing patterns (unit, integration, e2e)
- Deployment and release process

**Style & Architecture Standardization**
- Code style and formatting
- Architecture decisions (state management, data flow, etc.)
- Component/module organization
- Performance best practices
- Security guidelines

### 6. File Naming Convention
- Use kebab-case: `feature-name.mdc`
- Be specific: `api-authentication.mdc` not `auth.mdc`
- Group related rules: `backend-api-design.mdc`, `backend-error-handling.mdc`

### 7. Quality Checklist
Before finalizing the rule file:
- [ ] Is the rule actionable and specific?
- [ ] Does it include concrete examples?
- [ ] Is it relevant to the current project tech stack?
- [ ] Does it avoid redundancy with existing rules?
- [ ] Is the language clear and concise?
- [ ] Are there practical code snippets?

### 8. Example Output

For a request like "Create rules for adding new API endpoints", generate:

**File**: `.cursor/rules/backend-api-endpoints.mdc`

```markdown
---
alwaysApply: true
description: Standards for creating new API endpoints in FastAPI backend
---

# Backend API Endpoints

## Overview
Guidelines for implementing RESTful API endpoints in the FastAPI backend...

[Continue with full structure...]
```

## Notes
- Keep rules focused and scoped to specific areas
- Update existing rule files rather than creating duplicates
- Reference related rules using relative paths
- Include real code from the project as examples when possible
- Make rules prescriptive but flexible for edge cases
