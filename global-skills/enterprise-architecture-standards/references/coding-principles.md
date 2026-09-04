# Sound Coding & Algorithmic Principles

Covers: SOLID, DRY/KISS/YAGNI, design patterns (creational/structural/behavioral) and their overuse risks, clean code practices, algorithmic complexity awareness, code review standards.

## SOLID

- **Single Responsibility** — a class/module should have one reason to change. Test: can you describe what it does without using "and"? A `UserService` that handles validation, persistence, email sending, and analytics has four reasons to change and four reasons to break unexpectedly. Split by responsibility, not by arbitrary size.
- **Open/Closed** — open for extension, closed for modification. Achieve this through abstraction (interfaces, strategy pattern) at points that actually vary, not everywhere speculatively — see YAGNI below; don't build an extension point for a variation that doesn't exist yet.
- **Liskov Substitution** — a subtype must be usable anywhere its base type is expected without breaking correctness. A common violation: a subclass that throws on a method the base class documents as always succeeding (e.g., a `ReadOnlyList` extending `List` that throws on `add()`) — this signals the inheritance hierarchy itself is wrong, not just an implementation detail.
- **Interface Segregation** — many small, client-specific interfaces beat one large general-purpose interface that forces implementers to support methods they don't need (leading to empty/throwing stub implementations, a code smell that signals the interface should be split).
- **Dependency Inversion** — high-level modules (business logic) should depend on abstractions, not on low-level implementation details (a specific database driver, a specific HTTP client) — this is the same principle behind hexagonal/clean architecture in `software-architecture-styles.md`; apply it at genuine architectural seams, not by wrapping every single class in an interface reflexively.

## DRY, KISS, YAGNI — and their failure modes
- **DRY (Don't Repeat Yourself)** targets duplicated *knowledge*, not duplicated *text*. Two pieces of code that happen to look similar today but represent different business rules that could evolve independently should NOT be merged into one shared abstraction — that creates false coupling where a change for one use case unexpectedly breaks the other. The real test: if this business rule changes, should both call sites change together? If yes, share it. If no, duplication is the correct choice, even though it looks repetitive.
- **KISS (Keep It Simple)** — prefer the simplest design that correctly solves the actual problem. Simplicity is not "fewest lines" — a 200-line function with no structure is not simpler than 3 well-named 60-line functions; it's simplicity of *understanding* that matters.
- **YAGNI (You Aren't Gonna Need It)** — don't build configurability, abstraction layers, or generalized frameworks for requirements that don't exist yet. This is the single most common way "enterprise" code becomes bloated: a plugin system for a component with exactly one implementation, a configuration option nobody has ever needed to change, a generic `Repository<T>` abstraction hiding a straightforward query. Build for the requirement in front of you; refactor toward generality when a second real use case actually appears, not speculatively.

## Design patterns — use deliberately, not decoratively
Design patterns solve specific recurring problems; applying one where the underlying problem doesn't exist adds indirection with no benefit. For each pattern below, know the problem it solves — reach for it only when that specific problem is present.

**Creational** (object creation problems)
- *Factory Method / Abstract Factory* — when the concrete type to instantiate depends on runtime context and callers shouldn't know the concrete class. Overkill for a single concrete implementation with no foreseeable variants.
- *Builder* — for constructing complex objects with many optional parameters (avoids telescoping constructors). Unnecessary for objects with 2-3 straightforward fields.
- *Singleton* — use sparingly; it's frequently a disguised global mutable state problem that hurts testability. A dependency-injected shared instance (scoped by the DI container) usually achieves the same goal more testably than a true Singleton pattern.

**Structural** (composition problems)
- *Adapter* — when integrating an existing class with an incompatible interface, without modifying that class.
- *Decorator* — for adding behavior to individual objects dynamically (e.g., wrapping a data stream with compression, then encryption) without subclassing every combination.
- *Facade* — for providing a simple interface over a complex subsystem (e.g., one method call hiding several coordinated calls to different services). Genuinely useful for taming complexity, but don't let it become a god-object with too many responsibilities of its own.

**Behavioral** (communication/responsibility problems)
- *Strategy* — when an algorithm needs to vary independently of the client using it (e.g., different pricing rules selected at runtime). This is the real justification for an interface with multiple implementations — apply Open/Closed here, not everywhere.
- *Observer* — for one-to-many notification without tight coupling (often underlies event-driven architecture at the code level).
- *Command* — for encapsulating a request as an object (enables queuing, undo/redo, logging of operations) — a good fit for task queues and audit-logged actions.

## Clean code practices
- Names should reveal intent (`daysSinceLastLogin` not `d`); avoid needing a comment to explain what a poorly-named variable holds.
- Functions should do one thing at one level of abstraction; if a function needs a comment dividing it into "step 1 / step 2 / step 3" sections, those are usually three functions.
- Prefer guard clauses/early returns over deeply nested conditionals — nesting more than 2-3 levels deep is a strong signal to extract a function or invert the condition.
- Avoid magic numbers/strings — name them as constants with meaning (`MAX_RETRY_ATTEMPTS = 3`, not a bare `3` reused in five places with no shared name, which silently drifts out of sync when one gets changed and others don't).
- Comments should explain *why*, not *what* — code should be readable enough that *what* is self-evident; a comment restating the code in English is noise, but a comment explaining a non-obvious business reason or a workaround for an external system's quirk is valuable.
- Handle errors explicitly and specifically — don't swallow exceptions silently (`catch (e) {}`), and don't catch an overly broad exception type when a specific one is knowable, since that can mask unrelated bugs as if they were the expected failure case.

## Algorithmic complexity awareness
- Know the time/space complexity of the data structures and operations you're choosing, not just that the code "works" on a small test dataset — a solution that's O(n²) or worse on a collection that's small in dev/test but large in production is a specific, common, and entirely preventable source of production performance incidents.
- Choose the data structure that matches the actual access pattern: a hash map/set for O(1) average lookup instead of scanning a list repeatedly (a classic accidental-O(n²) bug is looking up inside a list, inside a loop, instead of building a lookup structure once); a sorted structure or index when range queries/ordering matter; a queue/stack when the access pattern is genuinely FIFO/LIFO.
- Be explicit about the complexity of code you write for data that will grow — "this works for 100 items" is not the same claim as "this works," if the real input can be 100,000 items; check that assumption against real/expected data volumes, not the sample size used while developing.

## Code review standards
- A reviewable change is a scoped one — prefer several small, focused pull requests over one enormous one; a huge diff gets a shallow review by exhaustion, which defeats the purpose of review.
- Review for: correctness against the actual requirement, the presence of both happy-path and non-happy-path test coverage (see `bdd-comprehensive-testing`), security implications (see `owasp-secure-coding-bdd`), and whether the change fits the existing architecture or silently works around it (a workaround that bypasses the established pattern is worth a conversation, not a silent merge).
- Leave actionable, specific feedback tied to the code, not vague style preferences dressed up as blocking issues — distinguish "this is a bug/security issue, must fix" from "this is a style preference, optional" explicitly so authors know what's actually required.
