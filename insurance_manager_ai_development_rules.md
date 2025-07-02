# Insurance Manager - AI Development Rules

General Rules:
- Try to avoid numbering things in code comments since it is annoying to change later.
- All future work, todos, notes to yourself, etc. should be put in the main todo list.  That is THE central repository for info you want to keep.

## Core Architecture Principles

1. **Extensibility Over Perfection** - Every system must be built with a plugin-based architecture that allows features to be added without modifying core code. Use interfaces, event buses, and JSONB fields liberally. The MVP should ship quickly while providing clear paths for future complexity.

2. **Start Simple, Scale Later** - Always implement the simplest version first. For example: 3 product tiers before custom products, 5 C-suite positions before full org charts, formula-based expansion before complex requirements. Features should be added through plugins, not by rewriting core systems.

3. **Feature Flags Everything** - New complexity must be hidden behind feature flags. The game should be playable with just MVP features, and advanced features should roll out progressively without breaking existing games.

## Implementation Guidelines

4. **JSONB for Future-Proofing** - Use PostgreSQL JSONB fields for any data that might become complex later. This includes: company preferences, product configurations, employee skills, regulatory details, turn results. Always include a schema_version field.

5. **Semester-Based Clean Slate** - The game resets completely between semesters, eliminating save game compatibility concerns. Within a semester, maintain data integrity and allow progression. Between semesters, feel free to make breaking changes, refactor schemas, and introduce new mechanics. Use this freedom to iterate rapidly based on student feedback.

6. **Plugin Pattern for Game Systems** - Every major feature (expansion, products, employees, investments) must implement the GameSystemPlugin interface. Communication between systems happens through events, never direct imports.

## Game Design Constraints

7. **Academic Rigor with Playability** - The simulation must be accurate enough for research papers while remaining engaging. Complex economic models (BLP demand) should have simple player-facing interfaces (sliders, not equations).

8. **Information Asymmetry is Key** - Many systems (especially investments) work through imperfect information. CFO skill affects what they perceive, not just mechanical multipliers. This creates natural progression and strategic depth.

9. **Regulatory Realism Without Overwhelm** - Implement real state insurance regulations but abstract them into 3 categories for MVP (strict/moderate/light). Full 51-state complexity comes later via plugins.

## Technical Standards

10. **Python 3.12 with Type Hints** - All Python code must use type hints. FastAPI for backend, Pydantic V2 for validation. No legacy Python patterns.

11. **Next.js 14 with TypeScript** - Frontend must use Next.js 14, React 18, TypeScript, Tailwind CSS, and shadcn/ui components. No custom CSS frameworks or exotic state management.

12. **PostgreSQL + Redis + Celery** - Data layer is PostgreSQL with TimescaleDB, Redis for caching/queues, Celery for async tasks. No other databases or job queues without strong justification.

## Development Workflow

13. **One Checkbox at a Time** - When working from the todo checklist, complete ONE item fully before moving to the next. Mark completed items with [x] and provide a summary.

14. **Preserve the Vision** - The blueprint describes both MVP and future vision. Always implement with the full vision in mind, but deliver only what's needed for the current phase.

15. **Document Extensibility Points** - When implementing any system, clearly document how it will be extended in the future. Add TODO comments for v2.0 features at natural extension points.

16. **Semester Configuration Management** - Each semester runs a specific version with its own configuration file. Features can be enabled/disabled per semester without code changes. Store semester configs in version control for reproducibility.

## Code Organization

17. **Strict Separation of Concerns** - Follow the prescribed directory structure:
   - `/core` - Stable engine that never imports from features
   - `/features` - Pluggable modules organized by game system
   - `/api` - Versioned endpoints (v1, v2 maintained in parallel)
   - `/config` - All configuration including feature flags

18. **Events Over Dependencies** - Features communicate through a central event bus, not by importing each other. This enables true modularity and prevents dependency hell.

## Testing & Quality

19. **Test the Plugin Interfaces** - Focus testing on the plugin interfaces and event contracts. If these work correctly, features can be swapped freely.

20. **Performance Budgets** - Turn processing must complete in <15 minutes even with 1000 players. Use caching, parallel processing, and database optimization from day one.

## Special Considerations

21. **CEO Progression Matters** - The CEO attribute system is central to player progression. It affects employees through multipliers and creates long-term goals. Don't simplify this system.

22. **Home State Advantage is Sacred** - Every player starts in their alma mater's state with significant advantages. This encourages mastery before expansion and must be preserved.

23. **Automated Systems Create Drama** - Many systems (like investment liquidation) are automated based on skill levels. This creates emergent storytelling through mechanical consequences.

## Anti-Patterns to Avoid

24. **No Complex UI Before Core Works** - Resist the urge to build elaborate visualizations before the core simulation runs correctly. Function before form.

25. **No Premature Optimization** - Don't optimize for millions of players before the game works for 10. But DO design the architecture to scale.

26. **No Feature Creep in MVP** - The blueprint contains many advanced features. Implement hooks for them but don't build them until Phase 10+. Ship the MVP first.

## Git Usage and Version Control

27. **No Submodules** - Keep everything in a single repository. Git submodules add complexity and frequently cause issues (as seen with the frontend). Use a monorepo structure instead.

28. **Meaningful Commit Messages** - Follow conventional commits format: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`. Include the affected system in brackets: `feat(investments): add CFO skill effects to portfolio perception`.

29. **Environment Files Strategy** - Always provide `.env.example` with all required variables. Never commit actual `.env` files. Use descriptive variable names and include comments explaining each variable's purpose.

30. **Migration Discipline** - Create separate migrations for each feature. Name migrations descriptively with timestamps. Test rollback procedures even though semesters reset. Never edit existing migrations - create new ones to fix issues.

31. **Feature Branch Workflow** - Create feature branches for each todo item. Keep PRs small and focused. Don't mix refactoring with new features. Always test the full game flow before merging.

## Database and Async Patterns

32. **Async All The Way** - FastAPI is async by design. Use `asyncpg` for database connections, not synchronous SQLAlchemy. If using connection pools, use `NullPool` for async compatibility, not `QueuePool`.

33. **Explicit Session Management** - Always use explicit database sessions. Pass `db: AsyncSession` as a dependency. Never use global database connections or implicit sessions.

34. **JSONB Schema Versioning** - Every JSONB field must include a `schema_version`. Create migration utilities to handle schema updates within semesters. Document the schema in comments above the field.

## Implementation Best Practices

35. **Check Before Building** - Always search the codebase first. Many features are already implemented in the simulations folder or as part of other systems. Don't recreate what already exists.

36. **Real Data Only** - Use real data whenever possible: actual university names, real state coordinates, accurate distances. Never use placeholder data that will need to be replaced later.

37. **Clean Up After Yourself** - Delete temporary files, test scripts, and debugging code before committing. The codebase will be public - keep it clean and professional.

38. **Error Handling Without Fallbacks** - Never hide errors with mock data or fallback values. If something fails, let it fail visibly. Fix the root cause instead of masking it.

39. **Save Intermediate Outputs** - All data processing pipelines should save intermediate results by default. This aids debugging and allows resuming failed processes.

## Frontend Development Patterns

40. **Trust the Backend** - The backend is complete and tested. Don't add client-side validation that duplicates backend logic. Let the backend be the single source of truth.

41. **Loading States Everywhere** - Every data fetch needs a loading state. Use skeleton loaders that match the shape of the expected content. Never show blank screens.

42. **Consistent Error Boundaries** - Wrap feature components in error boundaries. Show user-friendly error messages. Provide a way to retry or navigate away from errors.

43. **No Local State for Server Data** - Use TanStack Query for all server state. Only use local state for UI-specific concerns (modals, form inputs, etc.). Server state should always reflect the backend.

## Testing Strategy with Playwright

### Core Testing Principles

44. **Test User Journeys, Not Implementation** - Playwright tests should focus on complete user workflows (create CEO → expand to state → submit turn → view results) rather than individual component behavior.

45. **Visual Regression Testing** - Use Playwright's screenshot capabilities to catch UI regressions, especially for complex interfaces like the investment portfolio sliders and executive office dashboards.

46. **Test Information Asymmetry** - Create specific tests that verify novice vs expert CFOs see different information in the investment interface. This is core to the game's strategy layer.

### Critical User Flows to Test

47. **New Player Onboarding Flow**
   ```typescript
   test('complete character creation and first turn', async ({ page }) => {
     // Select academic background (RMI + second major)
     // Choose alma mater (determines home state)
     // Name company
     // Select starting line of business
     // Hire initial C-suite
     // Submit first turn decisions
     // Verify home state advantages applied
   });
   ```

48. **Turn Submission Deadline**
   ```typescript
   test('enforce Sunday midnight deadline', async ({ page }) => {
     // Submit partial decisions
     // Advance clock to 11:59 PM Sunday
     // Verify submission allowed
     // Advance to 12:01 AM Monday
     // Verify submission blocked
     // Confirm "no change" defaults applied
   });
   ```

49. **Investment Crisis Liquidation**
   ```typescript
   test('CFO skill affects liquidation choices', async ({ page }) => {
     // Create catastrophe triggering liquidation need
     // Test novice CFO (skill 30) - verify poor asset choices
     // Test expert CFO (skill 80) - verify optimal liquidation
     // Compare liquidation costs between skill levels
     // Verify UI shows liquidation report
   });
   ```

### Performance and Scale Testing

50. **Concurrent Player Testing**
   ```typescript
   test('100 concurrent players submit turns', async ({ browser }) => {
     const contexts = await Promise.all(
       Array(100).fill(null).map(() => browser.newContext())
     );
     // Each context represents a player
     // All submit decisions simultaneously
     // Verify no deadlocks or timeouts
     // Confirm turn processes within 15 minutes
   });
   ```

51. **State Machine Testing** - Test that game state transitions are valid:
   - Cannot submit decisions after deadline
   - Cannot hire employees without sufficient capital
   - Cannot expand without regulatory approval
   - Cannot offer products in unauthorized states

### Mobile and Accessibility Testing

52. **Mobile Responsiveness**
   ```typescript
   test.describe('Mobile gameplay', () => {
     test.use({ viewport: { width: 375, height: 667 }});
     
     test('executive offices navigation on mobile', async ({ page }) => {
       // Verify hamburger menu functionality
       // Test touch-based slider controls
       // Ensure decision forms are usable
       // Check financial reports readability
     });
   });
   ```

53. **Accessibility Compliance**
   ```typescript
   test('WCAG 2.1 AA compliance', async ({ page }) => {
     // Run axe-core accessibility scans
     // Verify keyboard navigation through all offices
     // Test screen reader announcements for turn results
     // Ensure color contrast ratios meet standards
   });
   ```

### Data Integrity Testing

54. **Financial Calculation Verification**
   ```typescript
   test('verify insurance economics calculations', async ({ page }) => {
     // Submit known pricing/product decisions
     // Trigger specific claim scenarios
     // Verify loss ratios match expected formulas
     // Confirm capital calculations are correct
     // Test adverse selection mechanics
   });
   ```

55. **Semester Reset Verification**
   ```typescript
   test('clean semester initialization', async ({ page }) => {
     // Verify all companies start fresh
     // Confirm no data persists from previous games
     // Check initial capital and settings
     // Validate semester configuration loaded correctly
   });
   ```

### WebSocket and Real-time Testing

56. **Turn Processing Notifications**
   ```typescript
   test('real-time updates during turn processing', async ({ page }) => {
     // Submit turn decisions
     // Monitor WebSocket messages
     // Verify progress updates received
     // Confirm completion notification
     // Check UI updates without refresh
   });
   ```

### Testing Best Practices

57. **Test Data Management** - Create factories for test data:
   - Company with specific CEO stats
   - Market conditions (boom/bust/catastrophe)
   - Competitor configurations
   - Semester-specific game configurations

58. **Parallel Test Execution** - Tests should be independent and run in parallel:
   - Each test creates its own game instance
   - No shared state between tests
   - Database transactions rolled back after each test
   - Use test-specific Redis namespaces

59. **Visual Testing Strategy**
   - Screenshot key interfaces at multiple breakpoints
   - Compare executive office themes for consistency
   - Verify chart/graph rendering accuracy
   - Test loading states and error conditions

60. **Performance Benchmarks** - Set specific targets:
   - Page load time < 3 seconds
   - Turn submission response < 500ms
   - Investment portfolio optimization < 2 seconds
   - Full turn processing < 15 minutes for 1000 players

These rules ensure consistent development that preserves the academic rigor and extensibility of the Insurance Manager while delivering a playable MVP on schedule. 