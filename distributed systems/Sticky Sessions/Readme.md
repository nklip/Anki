# Sticky Sessions

<sub>[Back to Distributed Systems](../Readme.md#content)</sub>

# Front

Why use sticky sessions, how do the three common pinning mechanisms work and fail, what are the four costs, and what is the stateless alternative?

# Back

**Sticky sessions (session affinity)** route a client's related requests to the **same application server** while affinity is valid and the server is available. This keeps requests near session state: data remembered between requests, such as a shopping cart.

## Why pin a client?

If server A alone holds your cart in memory, server B cannot continue that session. Pinning to A avoids shared-state fetches and can improve local cache reuse.

Compare the two designs: the upper flow returns to A; the lower flow lets A or B use the same shared session record.

![sticky-sessions.svg](images/sticky-sessions.svg)

## Three common pinning mechanisms

| Mechanism | How it pins | Weakness |
|---|---|---|
| **Balancer cookie** | The balancer sets a routing cookie; the client returns it. | Requires cookie support. Blocked, deleted, or expired cookies break affinity. |
| **Source-IP hash** | A repeatable calculation (hash) maps the client's Internet Protocol (IP) address to a server. | Network address translation (NAT) or proxies can group users on one IP and overload a server; IP changes can move users. |
| **Application session identifier (ID)** | The balancer reads a stable ID from a header, web address, or app cookie, then hashes it or looks up its server. | Every request needs the key. Server changes can remap hashes; lookup tables need storage and synchronization across balancers. |

These mechanisms select a server; **they do not copy session data**.

## How the balancer cookie works

1. **First request:** no routing cookie, so the balancer uses its normal algorithm and selects A.
2. **Response:** as A's response passes through, the balancer adds this example header:

   ```http
   Set-Cookie: SERVER_ID=A; Path=/; Secure; HttpOnly
   ```

3. **Later requests:** the browser stores the cookie and automatically includes it on matching requests:

   ```http
   Cookie: SERVER_ID=A
   ```

4. **Routing:** the balancer reads the cookie and sends the request to A again, while affinity is valid and A is healthy.

In `SERVER_ID=A`, `A` is the cookie value for server A. HAProxy lets you configure that cookie value on each server line. Because the cookie identifies the server, this design needs **no per-user mapping table**. Formats vary: AWS Application Load Balancer (ALB) encrypts target information in its cookie. If it cannot decode the cookie or the target is removed or unhealthy, ALB selects another target and updates the cookie.

## Four costs

1. **Uneven load:** busy clients stay pinned despite spare capacity elsewhere.
2. **Fragile failover:** after a failure or restart, requests may reach a different healthy server that lacks the old local session, losing the cart or requiring login again.
3. **Weaker elasticity:** added servers do not inherit pinned sessions; hash reassignment can separate clients from their state.
4. **Harder deployments and removal:** removing a server requires finishing sessions, moving state, or accepting resets. Draining in-flight requests alone cannot preserve sessions.

## Stateless alternative

Keep application servers **stateless between requests**: store session data in shared Redis or a database. Any healthy server uses the client's session ID, often in a cookie, to fetch the same state without pinning.

The shared store needs its own availability and durability design. Application servers become easier to balance, replace, and scale.

# Sources

- [MDN — Set-Cookie, Cookie, scope, and cookie attributes](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Cookies)
- [HAProxy — balancer-inserted cookies and per-server values](https://www.haproxy.com/documentation/haproxy-configuration-tutorials/proxying-essentials/session-persistence/)
- [NGINX — IP and key hashing, cookies, and learned session mappings](https://docs.nginx.com/nginx/admin-guide/load-balancer/http-load-balancer/)
- [NGINX — shared and changing IP limitations](https://docs.nginx.com/nginx-gateway-fabric/traffic-management/session-persistence/)
- [HAProxy — application keys, persistence, and table replication](https://www.haproxy.com/documentation/haproxy-configuration-manual/new/latest/intro/#3.3.6)
- [AWS — sticky cookies, failover, rebalancing, and request draining](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/edit-target-group-attributes.html#sticky-sessions)
- [Microsoft — affinity limits on load distribution and scaling](https://learn.microsoft.com/en-us/azure/architecture/guide/design-principles/scale-out)
- [Microsoft — local session storage, deployment costs, and shared stores](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/app-state?view=aspnetcore-10.0#session-state)
- [Redis — shared session storage and durability](https://redis.io/docs/latest/develop/use-cases/session-store/)
