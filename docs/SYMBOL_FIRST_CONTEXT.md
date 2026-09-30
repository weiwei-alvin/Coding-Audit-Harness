# Symbol-first Context Expansion

## Principle

When reading code for implementation, review, or debugging, **prioritize symbols (interfaces, signatures, types) over implementation bodies**. Expand context only when symbols are insufficient.

## Expansion Order

1. **Interface / Signature / Type / Symbol** (Priority 1)
   - Function signatures, class definitions, type aliases, interfaces
   - Public API surfaces
   - Schema definitions (JSON Schema, Protobuf, GraphQL, etc.)

2. **Implementation Body** (Priority 2 - only if #1 insufficient)
   - Function/method bodies
   - Private helpers
   - Algorithm details

3. **Callers / Callees** (Priority 3 - only if #2 insufficient)
   - Upstream callers (who calls this)
   - Downstream callees (what this calls)
   - Dependency graph traversal

## Rules

### No Fixed Token Hard Cap
- Do NOT set arbitrary token limits (e.g., "max 4000 tokens")
- Context size is determined by **information need**, not token budget
- Stop expanding when the question is answered

### Explicit Reason Required for Expansion
Every expansion beyond Priority 1 must have a documented reason:
- "Interface X doesn't specify error handling behavior"
- "Type Y is opaque, need to see implementation to understand invariants"
- "Caller Z passes unexpected parameter, need to trace call chain"

### Symbol-first in Practice

#### For Implementation Agent
```
Task: Implement login endpoint

1. READ: Interface/signature first
   - auth.py: LoginRequest, LoginResponse, AuthService.login()
   - types.py: User, Token, AuthError

2. ONLY IF NEEDED: Implementation
   - auth.py: login() method body
   - password hashing, token generation

3. ONLY IF NEEDED: Callers
   - routes.py: POST /login handler
   - middleware: auth validation
```

#### For Review Agent
```
Task: Review login implementation

1. READ: Interface/signature first
   - Does login() match AuthService interface?
   - Do types match expected contracts?

2. ONLY IF NEEDED: Implementation
   - Check password hashing uses bcrypt
   - Check token includes required claims
   - Check error handling matches AuthError type

3. ONLY IF NEEDED: Callers
   - Verify route handler calls login() correctly
   - Check middleware validates token properly
```

#### For Dependency Scheduler
```
Task: Determine ticket execution order

1. READ: Ticket interfaces (depends_on, API signatures)
   - T-001: provides AuthService interface
   - T-002: requires AuthService interface

2. NO NEED for implementation bodies
   - Dependencies declared in ticket frontmatter
```

## Anti-patterns to Avoid

| Anti-pattern | Why It's Wrong | Correct Approach |
|--------------|----------------|------------------|
| Reading entire files first | Wastes context on irrelevant details | Read signatures first, drill down only if needed |
| "Let me see the whole file" | No clear information goal | Define question first: "What does X return on error?" |
| Expanding to callers without reason | Caller context rarely changes interface understanding | Only trace callers when interface is ambiguous |
| Fixed token budgets | Forces premature truncation or over-reading | Expand until question answered |

## Tooling Support

### Recommended Read Patterns

```python
# GOOD: Symbol-first
read("src/auth.py", offset=0, limit=50)  # Signatures, class defs
# → If insufficient:
read("src/auth.py", offset=50, limit=100)  # Implementation

# GOOD: Targeted search
grep("class AuthService", "src/")
grep("def login", "src/auth.py")

# AVOID: Blind full-file reads
read("src/auth.py")  # No offset/limit - reads entire file
```

### LSP/IDE Integration
- Use "Go to Definition" for symbol navigation
- Use "Find References" for caller exploration
- Use "Type Hierarchy" for interface understanding

## Verification

During code review, verify:
- [ ] Agent cited specific signatures/interfaces before implementation details
- [ ] Any expansion beyond Priority 1 has explicit reason documented
- [ ] No arbitrary token limits mentioned in reasoning
- [ ] Context matches the question being answered

## Rationale

Symbol-first matches how experienced engineers read code:
1. Understand the **contract** (what does it do?)
2. Verify the **implementation** (how does it do it?)
3. Trace **dependencies** (what else is affected?)

This reduces cognitive load, speeds up comprehension, and prevents hallucination from over-reading irrelevant code.