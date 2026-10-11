# Design Patterns

<sub>[Back to Computer Science](../Readme.md#content)</sub>

**Design patterns describe reusable ways to organize objects and their interactions.** Here, an **interface** is a set of operations; a **client** is code that uses them. Wrapper is a broader term that overlaps several patterns.

## 1. Singleton

**Provide one instance of a class and a global access point to it.** The class controls construction so callers obtain the shared instance instead of creating their own. Java's `Runtime.getRuntime()` returns the application's single `Runtime` object. Use it when one shared instance is required.

## 2. Factory Method

**Let subclasses choose which concrete object to create.** A parent class calls a creation method returning a common interface; subclasses override that method. For example, a dialog calls `createButton()`, with platform-specific subclasses supplying different buttons. Its dialog logic stays the same. Not every static factory method is this pattern.

## 3. Builder

**Construct a complex object step by step, separating construction from the finished object.** In a common Java form, configure options on a builder, then call `build()`. For example, `HttpRequest.Builder` collects request settings and produces an immutable request. Method chaining is convenient, but alone does not define Builder.

## 4. Observer

**Notify registered listeners when something changes.** A subject, also called an observable, keeps track of observers and calls their notification methods after an event. For example, a data model notifies subscribed views to refresh. Observers can subscribe or unsubscribe; the subject uses their common notification interface.

```java
import java.util.ArrayList;
import java.util.List;

interface WeatherObserver {
    void onTemperatureChanged(int temperature);
}

class WeatherStation {
    private final List<WeatherObserver> observers = new ArrayList<>();
    private int temperature;

    void addObserver(WeatherObserver observer) {
        observers.add(observer);
    }

    void setTemperature(int temperature) {
        this.temperature = temperature;

        for (WeatherObserver observer : observers) {
            observer.onTemperatureChanged(this.temperature);
        }
    }
}
```
Usage inside `main`:
```java
WeatherStation station = new WeatherStation();

// Register two observers using lambdas
station.addObserver(t -> System.out.println("Phone: " + t + "°C"));
station.addObserver(t -> System.out.println("Website: " + t + "°C"));

// One change notifies both observers
station.setTemperature(25);
```
Output:
```text
Phone: 25°C
Website: 25°C
```

## 5. Strategy

**Make algorithms interchangeable behind one interface.** An object delegates work to a selected strategy instead of containing every algorithm itself. For example, a route planner uses either a walking or driving strategy. Switch the strategy to change the algorithm without rewriting the planner.

```java
List<String> words =
    new ArrayList<>(List.of("pear", "fig", "apple"));

// Strategy: compare by length
words.sort(Comparator.comparingInt(String::length));
System.out.println(words); // [fig, pear, apple]

// Strategy: compare alphabetically
words.sort(Comparator.naturalOrder());
System.out.println(words); // [apple, fig, pear]
```

## 6. State

**Make behavior depend on the object's current state.** The object delegates operations to a state object; a transition replaces that state. For example, a vending machine reacts differently to a purchase attempt before and after enough money is inserted. Strategy selects how to do a task; State represents a changing condition.

```java
interface State {
    State pressButton();
}

class Paused implements State {
    public State pressButton() {
        System.out.println("Starting playback");
        return new Playing();
    }
}

class Playing implements State {
    public State pressButton() {
        System.out.println("Pausing playback");
        return new Paused();
    }
}

class Player {
    private State state = new Paused();

    void pressButton() {
        state = state.pressButton();
    }
}
```

## 7. Adapter

**Translate an existing interface into the one a client expects.** An object adapter holds the existing object and translates calls to its methods. For example, a player expects `play()`, but an old audio library offers `startSong()`; the adapter connects them. The client can use the old library through its expected interface.

## 8. Decorator

* **Meaning**: An object that surrounds another object and provides access to it.
* **Purpose**: Could simplify usage, translate an interface, control access, or add behavior.
* **Interface**: May expose a different interface.
* **Composition**: Wrappers are not necessarily designed to stack.

## 9. Wrapper

* **Meaning**: A design pattern that wraps an object to add behavior.
* **Purpose**: Adds responsibilities without changing the wrapped class.
* **Interface**: Preserves the component interface, so clients can use the decorated object through the same type.
* **Composition**: Decorators can wrap other decorators to combine behaviors.

```java
InputStream input =
    new BufferedInputStream(new FileInputStream("data.txt"));
```

BufferedInputStream is both:
- A wrapper, because it holds another stream and reads from it.
- A decorator, because it adds buffering while remaining an InputStream.

# Sources

- [Gamma, Helm, Johnson, and Vlissides — Design Patterns, introduction and pattern intents (MIT-hosted book excerpt)](https://people.csail.mit.edu/addy/pattern/chap1.htm)
- [Microsoft — Design patterns: Singleton, Strategy, State, and their purposes](https://learn.microsoft.com/en-us/archive/msdn-magazine/2001/july/design-patterns-solidify-your-csharp-application-architecture-with-design-patterns)
- [Oracle — Runtime: one instance per Java application](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/lang/Runtime.html)
- [Microsoft — Simple Factory, Factory Method, and Abstract Factory](https://learn.microsoft.com/en-us/shows/visual-studio-toolbox/design-patterns-factories)
- [Microsoft — Observer: subscriptions and notifications](https://learn.microsoft.com/en-us/dotnet/standard/events/observer-design-pattern)
- [Oracle — HttpRequest.Builder: configuration steps and build()](https://docs.oracle.com/en/java/javase/25/docs/api/java.net.http/java/net/http/HttpRequest.Builder.html)
- [Microsoft — Adapter: exposing an existing class through another interface](https://learn.microsoft.com/en-us/shows/visual-studio-toolbox/design-patterns-adapterfaade)
- [Oracle — Decorator: wrapping, delegation, and a shared interface](https://www.oracle.com/technical-resources/articles/jones-owsm.html)
- [Oracle — BufferedInputStream: adding buffering to an existing stream](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/io/BufferedInputStream.html)
- [Oracle — Collection wrappers: delegation and additional functionality](https://docs.oracle.com/javase/tutorial/collections/implementations/wrapper.html)
- [Oracle — HttpServletResponseWrapper: “Wrapper or Decorator” terminology](https://docs.oracle.com/javaee/7/api/javax/servlet/http/HttpServletResponseWrapper.html)
