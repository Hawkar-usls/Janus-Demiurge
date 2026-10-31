# Policy-0A / C024: independent asymptotic *transfer* proof and theorem dependency audit

**Scope:** the precisely frozen JANUS \`Policy0A\` on the padded directed
graph-tautology family \`H_n\`. **Not** a lower bound against arbitrary SAT
algorithms, arbitrary resolution, CDCL, or Policy-0B. \`P_VS_NP = OPEN\`.

**Status:** all-n reduction re-derived independently from the source
implementation, modulo the externally published FCWS \`GT_n\` theorem.
**Not claimed:** independent original proof of that external theorem, a
machine-checked arbitrary-depth projection induction, or new P-vs-NP research
breakthrough. These are deliberately distinct evidence gates.

## 1. Source identities (read as data, not executed)

- Beame, Impagliazzo, Pitassi, Segerlind (2010), *Formula Caching in DPLL*,
  Definition 4.24, Lemmas 4.26–4.27, Theorem 4.28, journal pages 9:27–9:29:
  https://www.cs.toronto.edu/~toni/Papers/memoization.pdf
- \`Hawkar-usls/Janus-Fundamentum\`:
  \`experiments/direct/janus_tear_policy0a_masked_tseitin.py\`,
  verified Git blob \`c3684f9cc8a7f3d5470d2218bf9296310ad317e9\`.
- \`Hawkar-usls/TOPA\`:
  \`research/mathematics/p-vs-np/source_gt.py\`,
  blob \`fc3ad084944aa303da3ec64b64c637d3cdf24e2a\`;
  \`research/mathematics/p-vs-np/policy0a_padded_gt_counterfamily.py\`,
  blob \`9002e5b96724fe6534af08cd881264351481623a\`.

These identifiers are *version fences* for the argument. Any change in
the referenced Policy0A implementation must force a new parity review.

## 2. Mathematical definitions

Fix integer \`n>=3\`. Directed \`GT_n\` uses \`n(n-1)\` variables
\`x_(i,j)\`, \`i!=j\`. Its clauses are:
- for unordered pairs \`{i,j}\`: \`x_ij OR x_ji\` and
  \`NOT x_ij OR NOT x_ji\`;
- for ordered distinct triples \`(i,j,k)\`:
  \`NOT x_ij OR NOT x_jk OR x_ik\`;
- for each \`j\`: \`OR_(i!=j) x_ij\`.

This directly implements Definition 4.24 (GOP on the complete graph plus
totality); it is **not** the distinct compact unordered-pair encoding also
used elsewhere in Fundamentum. The source has

\`\`\`text
V = n(n-1)
core_clauses = n((n-1)^2+1)
L_GT = 3n(n-1)^2
\`\`\`

Construct \`H_n = GT_n AND BOOST_n AND SINK_n\` on fresh padding
variables, with

\`\`\`text
B=256n^2; p=64n^2
BOOST: (x OR b_x,t), for every directed x and 1<=t<=B
SINK:  (d OR a OR u_i), (~d OR ~a OR v_j), 1<=i,j<=p
\`\`\`

All \`b,u,v,d,a\` variables are distinct and have no other occurrences.
Variable IDs place \`d=1,a=2\` before all other variables.

## 3. Freeze actual Policy-0A semantics

The registered solver invokes \`visible_affine_root_decision\` once at the
root, then recursively: exhaustive unit propagation; exact pre-resolution
CNF cache; one bounded local Resolution pass; exhaustive UP; highest
literal-frequency variable (smallest ID ties); branch false then true.

The local Resolution pass enumerates pivots in increasing variable order.
Each complementary parent pair increments an attempt counter *before*
testing for tautology or width; the cap is \`max(64,4L(K))\`, with \`L\`
the current number of literal occurrences. No learned clauses persist
across sibling branches except the explicit exact cached answers.

**Freeze invariant:** a changed order of source operations, a new
reason cache, additional simplification, a different branch policy, or
a different Resolution budget invalidates this transfer. The proof is
not portable to an unidentified future implementation.

## 4. Root affine shortcut does not apply (all n)

Each distinct private booster scope \`{x,b}\` contains exactly one
clause \`(x OR b)\`. Its allowed bit assignments are
\`{(0,1),(1,0),(1,1)}\`, of cardinality three. A nonempty affine
space over \`GF(2)\` has \`2^k\` points and cannot have three.

The frozen root detector requires **every** source clause to be
covered by an exact affine scope relation. None of these private
2-variable booster scopes is affine; consequently not all clauses
are covered, and the root decision is \`None\`. The recursive solver
must run. This holds for every n>=3.

## 5. Exact all-n integer algebra — no extrapolation from finite tests

\`\`\`text
L_boost = 2 n(n-1) * 256 n^2 = 512 n^3(n-1)
L_sink = 6p = 384 n^2

L0 = L_GT + L_boost + L_sink
   = 512 n^4 - 509 n^3 + 378 n^2 + 3n

p^2 - 4L0
   = 2048 n^4 + 2036 n^3 - 1512 n^2 - 12 n
   = 4n(512n^3 + 509n^2 - 378n - 3).
\`\`\`

For n>=3, \`509n-378>0\` and \`512n^3>3\`, so the
parenthesized term is strictly positive. Also \`p^2>64\`.
Hence

\`\`\`text
p^2 > max(64,4L0)
\`\`\`

for **every** n>=3.

Our independent polynomial checker also substitutes \`n=m+3\`, writes
the exact resulting integer coefficients, and requires *every*
coefficient of the slack to be nonnegative with positive constant.
This is a symbolic positivity certificate, not testing n=3..N.

At the first pivot \`d\` there are \`p^2\` complementary parent pairs;
every resolvent contains both \`a\` and \`~a\`, so no clause is added.
The counter is nevertheless consumed before the tautology test.

## 6. All-depth induction: resolution remains inactive

**Invariant at every reachable nonterminal key:** no padding-only
resolution inference has been added, the entire sink remains
untouched, and its \`p^2\` pairs are visited before any core pivot.

**Base:** no core or padding variable was assigned; the sink is
untouched; the previous exact inequality applies.

**Step:** recursive branching is on a core variable (proved next).
Restricting a CNF by a truth assignment only deletes clauses or
literals. Exhaustive UP performs more such restrictions. The private
sink has no shared core variables, no sink unit clauses, and is never
chosen as a branch variable. It therefore remains unchanged at each
nonterminal child, while the child's literal count is <= L0.

Thus \`max(64,4L(K)) < p^2\` remains true. The next Resolution
pass again exhausts its budget on the first sink pivot \`d\`, adding
zero clauses. By induction no core Resolution is ever executed.

## 7. All-depth induction: core-only branching and projection

An unassigned core variable \`x\` still has all \`B\` private
\`(x OR b)\` clauses. Hence

\`\`\`text
frequency(x)>=B=256n^2;
frequency(d)=frequency(a)=2p=128n^2;
frequency(private padding leaf)<=1.
\`\`\`

The strict gap \`B>2p\` forces highest-frequency branching into
a surviving core variable. Each core variable has the same booster
offset \`B\`, so frequency ordering *among* the core variables matches
the isolated \`GT_n\` ordering.

Let \`P(K)\` retain exactly the clauses of pre-resolution key \`K\`
whose variables lie entirely inside the directed core.

**Base:** before branching, neither the boosters nor sink contribute
core-only clauses, and \`P(K)=unitprop(GT_n)\`.

**Step:** branching on core variable \`x\` restricts exactly the
same core clauses in both executions. A booster becomes either
satisfied (x=1) or a private positive unit (x=0); its forced leaf
cannot constrain another core variable. The sink is untouched,
and by section 6 there are no added resolution clauses.
Exhaustive UP therefore yields

\`\`\`text
P(K_child)=unitprop(GT_n restricted by accumulated core decisions).
\`\`\`

The selected branching variable and false-first/true-second order
also coincide. The augmented exact cache can sometimes reuse
*fewer* states than isolated GT, but it cannot confuse two
different core states: \`K1=K2 => P(K1)=P(K2)\`.
Consequently the projected recursion is an admissible exact
Formula Caching refutation of the theorem-matched \`GT_n\`.

## 8. Lower-bound transfer (explicit published-theorem dependency)

Beame et al. Theorem 4.28 proves for that very directed \`GT_n\`
that every FCWS refutation requires at least \`2^(n-2)\` nodes.
The theorem proof identifies that many distinct residual formulas
at novelty level \`n-2\`; this is stronger than merely saying that
some search visits that many repeated nodes. Basic exact FC is
a restricted instance of FCWS.

By the all-depth projection invariant, each distinct projected
core residual must occur at a distinct augmented exact
pre-resolution key. Therefore, **assuming the published Theorem
4.28 and the frozen semantics described in section 3**,

\`\`\`text
S(H_n) >= 2^(n-2).
\`\`\`

This is a *complete mathematical deduction from the published
theorem*, not a newly independent proof of Theorem 4.28 itself.
No step here proves an exponential lower bound for arbitrary
Resolution: the original GT family has short regular Resolution
proofs, consistent with the paper.

## 9. Bit-length and superpolynomial transfer

Exact number of clauses and maximum variable ID:

\`\`\`text
clauses(H_n) = 256n^4 -255n^3 +126n^2 +2n
max_var(H_n) = 256n^4 -256n^3 +129n^2 -n +2.
\`\`\`

For any signed-binary integer-literal list with self-delimiting
clause separators, these are \`O(n^4)\` quantities and each
literal ID uses \`O(log n)\` bits. Therefore

\`\`\`text
N_n = bits(H_n) = O(n^4 log n).
\`\`\`

For each fixed \`c\`, \`N_n^c\` is bounded by a polynomial in n,
whereas \`2^(n-2)\` grows faster than every polynomial.
So \`S(H_n)\` is not bounded by \`N_n^c\` uniformly in n.

**Conclusion only for the frozen Policy-0A:**

\`\`\`text
UNIVERSAL_POLYNOMIAL_RESIDUAL_COUNT_FOR_CURRENT_POLICY0A = REFUTED
P_VS_NP = OPEN
\`\`\`

## 10. Epistemic gate summary

| Gate | Independent evidence | Claim ceiling |
|---|---|---|
| Exact source encoding | Rebuilt directed clauses and checked counts on n=3..6 | finite structural crosscheck |
| R0 root affine | three-point non-affine relation and source-code semantics | all n>=3 conditional on frozen detector |
| R1 local Resolution starvation | exact polynomial identity, strict shifted-coefficient positivity | all n>=3 |
| R2 branch priority | exact frequency gap \`128n^2\` | all n>=3 |
| R3 core projection | written all-depth induction with exact cache-injection argument | human mathematical derivation |
| R4 published GT lower bound | actual journal Theorem 4.28, pages 9:28–9:29 | external peer-reviewed theorem, **not independently reproved** |
| R5 bit complexity | exact polynomial clause and variable counts | all n>=3 |
| R6 model parity | frozen implementation source fingerprints, CI source hash checks | exact current Policy-0A only |

**What remains genuinely open:** an entirely new standalone proof of
the journal GT theorem (not required for a standard mathematical
reduction that cites it), independent *formal proof-assistant*
verification of the projection induction, and refutation/analysis of
different proof systems. None of these authorizes \`P=NP\` or \`P!=NP\`.
