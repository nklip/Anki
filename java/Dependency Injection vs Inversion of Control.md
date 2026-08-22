# Dependency Injection vs. Inversion of Control

## Front

What is the difference between **Dependency Injection (DI)** and **Inversion of Control (IoC)**?

## Back

**Inversion of Control is the general principle. Dependency Injection is one technique for applying it.**

### Inversion of Control (IoC)

IoC means that control is transferred from application code to an external component, framework, or runtime.

The external component may control:

- Object creation and lifecycle.
- Which implementation is used.
- When application code is called.
- How components are connected.

Examples include dependency injection, framework callbacks, event handlers, and template methods.

### Dependency Injection (DI)

DI means that an object receives its dependencies from the outside instead of constructing or locating them itself.

DI can be performed manually; an IoC container is not required.

### Without dependency injection

```java
final class OrderService {
    private final PaymentGateway gateway =
            new StripePaymentGateway();

    void placeOrder(Order order) {
        gateway.charge(order.total());
    }
}
```

`OrderService` creates its own dependency and is tightly coupled to `StripePaymentGateway`.

### With constructor injection

```java
final class OrderService {
    private final PaymentGateway gateway;

    OrderService(PaymentGateway gateway) {
        this.gateway = gateway;
    }

    void placeOrder(Order order) {
        gateway.charge(order.total());
    }
}
```

The dependency is supplied at the composition root:

```java
PaymentGateway gateway = new StripePaymentGateway();
OrderService service = new OrderService(gateway);
```

For a test, it can be replaced easily:

```java
PaymentGateway gateway = new FakePaymentGateway();
OrderService service = new OrderService(gateway);
```

### Comparison

| Inversion of Control | Dependency Injection |
|---|---|
| Broad design principle | Specific implementation technique |
| Answers: **Who controls creation, lifecycle, or execution?** | Answers: **How does an object obtain its dependencies?** |
| Control moves outside the component | Dependencies are supplied from outside the object |
| Includes DI, callbacks, events, and template methods | Commonly uses constructor, setter, or field injection |
| Often implemented by a framework or container | Can be performed manually or by a container |

### Injection styles

1. **Constructor injection** — preferred for required dependencies; supports immutability and makes dependencies explicit.
2. **Setter injection** — useful for optional or replaceable dependencies.
3. **Field injection** — usually discouraged because dependencies are hidden, mutation is easier, and isolated testing is harder.

### Important distinction

A DI container demonstrates both concepts:

- It applies **IoC** by controlling object creation, wiring, and lifecycle.
- It performs **DI** by passing dependencies into those objects.

### Key idea

> **IoC is the principle: “control comes from outside.”**  
> **DI is the mechanism: “dependencies come from outside.”**

DI is a form of IoC, but IoC is broader than DI.
