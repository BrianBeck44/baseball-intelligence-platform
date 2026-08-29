# ADR-001: Frontend Framework — React + TypeScript

**Status:** Accepted
**Date:** 2026-08-29

## Context

The Baseball Intelligence Platform requires a modern frontend framework for building the user-facing analytics application.

The developer has existing professional experience with Vue.js but wants the project to provide additional experience with React because React is widely used across current software engineering job opportunities.

The project should therefore provide meaningful React experience while allowing existing frontend knowledge to transfer to the new framework.

## Decision

We will use **React with TypeScript** for the frontend application.

The frontend stack will consist of:

* React
* TypeScript
* Tailwind CSS

## Rationale

React was selected because:

1. It provides significant exposure to a widely used frontend ecosystem.
2. Existing Vue.js experience provides transferable knowledge of component-based UI development.
3. The project can be used to develop practical experience with React-specific patterns and architecture.
4. TypeScript provides experience with strongly typed frontend development.
5. React + TypeScript is a strong complement to the project's Python/FastAPI backend.

## Expected React Learning Objectives

The project will intentionally provide experience with:

* Functional components
* Props
* State management
* Hooks
* `useState`
* `useEffect`
* Component composition
* React Router
* API integration
* Error and loading states
* Forms
* TypeScript interfaces and types
* Testing React components

## Alternatives Considered

### Vue.js

**Advantages:**

* Existing experience
* Faster initial development
* Familiar component model

**Disadvantages:**

* Provides less opportunity to expand the developer's frontend skill set.

Vue.js was therefore not selected for this project.

### React + JavaScript

React with JavaScript would provide the desired React experience.

However, TypeScript was selected because the project is also intended to demonstrate modern frontend engineering practices and provide additional experience with strongly typed applications.

## Consequences

### Positive

* Adds practical React experience to the developer's existing Vue.js skill set.
* Adds TypeScript experience.
* Creates a more broadly applicable frontend portfolio project.
* Provides opportunities to demonstrate modern React architecture and testing.

### Negative

* Initial frontend development will be slower while learning React-specific patterns.
* Some concepts already familiar from Vue.js will need to be learned using React's conventions.

## Related Decisions

* **ADR-002:** Primary Baseball Data Source
* **ADR-003:** Database Architecture
* **ADR-004:** Data Ingestion Architecture
* **ADR-005:** FastAPI Application Architecture
