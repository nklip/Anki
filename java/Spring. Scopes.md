# Spring. Scopes

## Front

What does a Spring bean's scope control, and what do the built-in scopes mean?

## Back

A bean's **scope** controls how many instances Spring creates and how long each instance is reused. `singleton` is the default: one instance per bean definition per Spring container, not one object for the whole JVM.

![How Spring bean scopes choose a sharing boundary](svg/spring-bean-scopes.svg)

- `singleton`: one shared instance per bean definition and container; normally used for stateless services.
- `prototype`: a new instance whenever the container is asked for that bean. Spring creates and configures it, but does not run its configured destruction callbacks.
- `request`: one instance per HTTP request.
- `session`: one per HTTP session.
- `application`: one per `ServletContext`.
- `websocket`: one per WebSocket session.

The four web scopes require a web-aware `ApplicationContext`.

Annotation fragment:

```java
@Component
@Scope(ConfigurableBeanFactory.SCOPE_PROTOTYPE)
class ReportBuilder {}
```

A singleton's dependencies are normally injected once. To access a shorter-lived bean repeatedly, use a scoped proxy or `ObjectProvider<T>` instead of assuming direct injection creates a fresh object.

## Sources

- [Spring Framework: Bean Scopes](https://docs.spring.io/spring-framework/reference/core/beans/factory-scopes.html)
- [Spring Framework API: `@Scope`](https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/context/annotation/Scope.html)
