# Chapter 4: Design a Rate Limiter
<sub>[Back to System Design](../Readme.md#content)</sub>

## Introduction

This chapter explores the design and implementation of a rate limiter — a system component used to control traffic rates sent by clients or services. Rate limiters are crucial for preventing abuse, reducing costs, and ensuring the stability of server resources. Examples of their use include limiting posts, account creations, and reward claims.

## Benefits of Rate Limiting

- **Preventing Denial of Service (DoS) attacks:** [[1]](#ref-1) Blocking excess calls to avoid resource starvation.
- **Cost Reduction:** Limiting unnecessary requests to reduce server expenses.
- **Preventing Overloads:** Filtering out excessive requests to stabilize server performance.

## Step 1: Understand the Problem and Establish Design Scope

### Key Features
- Server-side API rate limiter.
- Support for multiple throttle rules.
- Handle large-scale systems in distributed environments.
- Option for a standalone service or application-level code.
- Inform users when throttled.

### Requirements

- Accurate request throttling.
- Minimal latency.
- Low memory usage.
- Distributed capability.
- Clear exception handling.
- High fault tolerance.

## Step 2: Propose a High-Level Design and Get Buy-In

### Placement Options

<div style="margin-left:1rem">
    <img src="./images/hld-architecture.svg" alt="hld-architecture.svg" width="1000">
</div>

1. **Client-Side Implementation:** Unreliable due to potential misuse.
2. **Server-Side Implementation:** Preferred for control and reliability.
3. **Middleware (API Gateway):** A flexible option for integrated rate limiting.

### Guidelines for Placement
- Evaluate the current tech stack and choose efficient options.
- Select appropriate algorithms based on business needs.
- Use an API gateway if microservices are employed.
- Opt for commercial solutions if resources are limited.

## Algorithms for Rate Limiting

List of popular algorithms:
1. Token bucket.
2. Leaking bucket.
3. Fixed window counter.
4. Sliding window log.
5. Sliding window counter.

### 1. Token Bucket

Both Amazon [[5]](#ref-5) and Stripe [[6]](#ref-6) use this algorithm to throttle their API requests.

<div style="margin-left:1rem">
  <img src="./images/token-bucket.svg" alt="token-bucket.svg" width="1000">
</div>

- **Description:** Tokens are added to a bucket at a fixed rate; each request consumes a token.
- **Parameters:** Bucket size and refill rate.
- **Pros:** Easy to implement, memory-efficient, supports traffic bursts.
- **Cons:** Requires careful parameter tuning.

The image below illustrates how token consumption, refill, and rate-limiting logic work. In this example, the token bucket size is 4, and the refill rate is 4 tokens per minute.

<div style="margin-left:1rem">
  <img src="./images/token-bucket-steps.svg" alt="token-bucket-steps.svg" width="1000">
</div>

### 2. Leaking Bucket

Shopify, an e-commerce company, uses leaky buckets for rate limiting [[7]](#ref-7).

<div style="margin-left:1rem">
  <img src="./images/leaking-bucket.svg" alt="leaking-bucket.svg" width="1000">
</div>

- **Description:** Processes requests at a fixed rate using a FIFO queue.
- **Pros:** Memory-efficient, stable outflow rate.
- **Cons:** Traffic bursts may delay recent requests.

Example: https://github.com/uber-go/ratelimit

### 3. Fixed Window Counter

<div style="margin-left:1rem">
  <img src="./images/fixed-window-counter.svg" alt="fixed-window-counter.svg" width="1000">
</div>

- **Description:** Divides time into fixed intervals and uses counters to limit requests.
- **Pros:** Simple, efficient for specific use cases.
- **Cons:** Traffic spikes at window edges can exceed limits.

- A sudden burst of traffic at the edges of time windows
could allow more requests than the allotted quota.

<img src="./images/fixed-window-issue.svg" alt="fixed-window-issue.svg" width="1000">

### 4. Sliding Window Log

<div style="margin-left:1rem">
  <img src="./images/sliding-window-log.svg" alt="sliding-window-log.svg" width="1000">
</div>

- **Description:** Tracks timestamps to allow a rolling time window.
- **Pros:** Accurate rate limiting.
- **Cons:** High memory consumption.

### 5. Sliding Window Counter

<div style="margin-left:1rem">
  <img src="./images/sliding-window-counter.svg" alt="sliding-window-counter.svg" width="1000">
</div>

- **Description:** Combines fixed window and sliding log methods for smoothing spikes.
- **Pros:** Memory-efficient, handles traffic bursts.
- **Cons:** Approximation may not be perfectly strict.

## Step 3: Design Deep Dive

<div style="margin-left:1rem">
  <img src="./images/architecture.svg" style="margin-left: 40px; margin-top: 40px; margin-bottom: 20px;" alt="architecture.svg" width="1000">
</div>

- **Data Storage:** Use in-memory caching (e.g., Redis) for fast counter operations.
- **Steps:**
  1. The client sends a request to the middleware.
  2. The middleware checks counters in Redis.
  3. The request is processed or rejected based on limits.

## Advanced Considerations

### Distributed Environments
- **Challenges:** Race conditions, synchronization issues.
- **Solutions:** Use locks, Lua scripts [[13]](#ref-13), or sorted sets in Redis [[8]](#ref-8). Employ centralized data stores for synchronization.

### Performance Optimizations
- Multi-data center setups for reduced latency.
- Eventual consistency models for synchronization.

### Monitoring
- Regular analytics to ensure algorithm effectiveness and adjust rules as needed.

## Step 4: Wrap up

Additional talking points:
* Hard vs soft rate limiting:
  - Hard: The number of requests cannot exceed the threshold.
  - Soft: Requests can exceed the threshold for a short period.
* Rate limiting at different levels. It is possible to apply rate limiting at other layers. For example, you can apply rate limiting by IP address using iptables [[15]](#ref-15) (IP: layer 3).
* Avoid being rate limited.

> Note: The Open Systems Interconnection model (OSI model) has 7 layers [[16]](#ref-16):
> * Layer 1: Physical layer
> * Layer 2: Data link layer
> * Layer 3: Network layer
> * Layer 4: Transport layer
> * Layer 5: Session layer
> * Layer 6: Presentation layer
> * Layer 7: Application layer

## Reference materials

1. <a id="ref-1"></a>[Rate-limiting strategies and techniques](https://cloud.google.com/solutions/rate-limiting-strategies-techniques)
2. <a id="ref-2"></a>[Twitter rate limits](https://developer.twitter.com/en/docs/basics/rate-limits)
3. <a id="ref-3"></a>[Google docs usage limits](https://developers.google.com/docs/api/limits)
4. <a id="ref-4"></a>[IBM microservices](https://www.ibm.com/cloud/learn/microservices)
5. <a id="ref-5"></a>[Throttle API requests for better throughput](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html)
6. <a id="ref-6"></a>[Stripe rate limiters](https://stripe.com/blog/rate-limiters)
7. <a id="ref-7"></a>[Shopify REST Admin API rate limits](https://help.shopify.com/en/api/reference/rest-admin-api-rate-limits)
8. <a id="ref-8"></a>[Better Rate Limiting With Redis Sorted Sets](https://engineering.classdojo.com/blog/2015/02/06/rolling-rate-limiter/)
9. <a id="ref-9"></a>[System Design — Rate limiter and Data modelling](https://medium.com/@saisandeepmopuri/system-design-rate-limiter-and-data-modelling-9304b0d18250)
10. <a id="ref-10"></a>[How we built rate limiting capable of scaling to millions of domains](https://blog.cloudflare.com/counting-things-a-lot-of-different-things/)
11. <a id="ref-11"></a>[Redis website](https://redis.io/)
12. <a id="ref-12"></a>[Lyft rate limiting](https://github.com/lyft/ratelimit)
13. <a id="ref-13"></a>[Scaling your API with rate limiters](https://gist.github.com/ptarjan/e38f45f2dfe601419ca3af937fff574d#request-rate-limiter)
14. <a id="ref-14"></a>[What is edge computing](https://www.cloudflare.com/learning/serverless/glossary/what-is-edge-computing/)
15. <a id="ref-15"></a>[Rate Limit Requests with Iptables](https://blog.programster.org/rate-limit-requests-with-iptables)
16. <a id="ref-16"></a>[OSI model](https://en.wikipedia.org/wiki/OSI_model#Layer_architecture)
