# SOLID

<sub>[Back to Computer Science](../Readme.md#content)</sub>

# Front

What design problem does each SOLID principle address?

# Back

**SOLID** names five design principles for keeping changes local, replacements reliable, and business rules independent of technical details. A **module** is a unit of code; a **client** uses it. An **interface** lists operations; its **contract** includes their promised behavior.

## S — Single Responsibility Principle

**Group code by one coherent reason to change.** An actor is a stakeholder group with a shared business responsibility. Read each row below: separate payroll, reporting, and storage because different actors change their requirements independently. One responsibility can need several methods.

![solid-single-responsibility.svg](images/solid-single-responsibility.svg)

## O — Open–Closed Principle

**Add an expected variation without rewriting established logic.** Below, `Checkout` uses `DiscountPolicy`; a new seasonal implementation supplies the same operation and preserves its contract. Configuration can select it. This protects a chosen extension point; bug fixes and other edits remain valid.

![solid-open-closed.svg](images/solid-open-closed.svg)

## L — Liskov Substitution Principle

**A replacement must honor the contract clients rely on.** Below, `Rectangle` promises independent width and height setters. A `Square` that changes both dimensions breaks that promise: the client expects area 20 but gets 16. Separate shapes with fixed dimensions can share an `area()` contract instead.

![solid-liskov-substitution.svg](images/solid-liskov-substitution.svg)

A substitute must not demand more before a call, guarantee less afterward, or break promised state rules. This also applies to interface implementations; the example concerns these setters, not every square–rectangle model.

## I — Interface Segregation Principle

**Clients should depend only on capabilities their role needs.** Below, a print job uses `Printer`, without depending on scan or fax operations. Devices can implement several interfaces. Split by client needs, not by a universal one-method-per-interface rule.

![solid-interface-segregation.svg](images/solid-interface-segregation.svg)

## D — Dependency Inversion Principle

**Business policy and technical details should depend on abstractions, which must not depend on those details.** An abstraction expresses the client's needs. Below, `OrderService` uses `OrderRepository`; the storage class implements it. Arrows show source-code dependencies: the service still calls storage at runtime.

![solid-dependency-inversion.svg](images/solid-dependency-inversion.svg)

**Dependency injection** supplies a collaborator from outside. Injecting a concrete storage type still couples the service to that type; injection alone does not establish dependency inversion.

# Sources

- [Robert C. Martin — The Single Responsibility Principle](https://blog.cleancoder.com/uncle-bob/2014/05/08/SingleReponsibilityPrinciple.html)
- [Robert C. Martin — The Open Closed Principle](https://blog.cleancoder.com/uncle-bob/2014/05/12/TheOpenClosedPrinciple.html)
- [Barbara Liskov and Jeannette Wing — A Behavioral Notion of Subtyping](https://www.cs.cmu.edu/~wing/publications/LiskovWing94.pdf)
- [Robert C. Martin — Design Principles and Design Patterns; author-attributed PDF mirror](https://cdn2.f-cdn.com/files/download/625001/XQ4sUPrinciples_and_Patterns.pdf)
- [Robert C. Martin — SOLID Relevance](https://blog.cleancoder.com/uncle-bob/2020/10/18/Solid-Relevance.html)
- [Robert C. Martin — The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Martin Fowler — Inversion of Control Containers and the Dependency Injection pattern](https://martinfowler.com/articles/injection.html)
