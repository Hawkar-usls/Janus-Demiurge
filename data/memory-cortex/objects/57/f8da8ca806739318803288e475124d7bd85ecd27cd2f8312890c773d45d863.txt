# JANUS Sobek–Anubis control and myth-source protocol v0.3

## Purpose

This amendment protects the Sobek morphology program from two distinct failure modes:

1. **visual identity confounds**, especially canid-headed deities versus crocodilian-headed Sobek under low resolution, damage, stylisation or algorithmic reduction; and
2. **narrative conflation**, where modern retellings merge the dismemberment of Osiris, the recovery of Horus's hands, the injury/restoration of the Eye of Horus, and solar Sobek-Re material into one apparently coherent story that is not supported by a single ancient witness.

The protocol is deliberately conservative. A plausible story is not promoted merely because its parts are individually Egyptian.

## 1. Canid controls are mandatory

Anubis may appear as a full recumbent canid or as a human with a canid/jackal-like head. The Metropolitan Museum also warns that Egyptian divine canid representations need not map cleanly onto modern zoological species, and similar heads can identify Anubis, Wepwawet or Duamutef depending on context.

Therefore the future Sobek blind image experiment must include a **CANID_DEITY_CONTROL** class, not an `ANUBIS_ONLY` class.

Frozen minimums:

- >=20 canid-deity controls total;
- >=8 objects explicitly identified as Anubis after unblinding;
- >=6 Wepwawet/other canid controls where source eligibility permits;
- include full-animal and anthropomorphic-head modes;
- include at least one low-resolution/damaged/schematic stress stratum.

Primary morphological separation:

- CANID: pointed erect ears where preserved, narrow tapering mammalian muzzle, canid nose, paws/long mammalian limbs, frequent recumbent funerary posture.
- CROCODILIAN: broad/flattened rostrum, crocodilian jaw proportions, no tall pointed canid ears, low elongated reptilian body and tail when preserved.

Crown, sun disk, uraeus, ankh, was-scepter, black colour and funerary placement remain **context-only features** and cannot carry identity by themselves.

## 2. Confusion matrix, not a single accuracy score

The classifier report must expose at least:

- Sobek sensitivity;
- Sobek specificity;
- Sobek vs canid-deity confusion;
- Sobek vs generic/non-Sobek crocodile confusion;
- crown-only performance;
- crocodilian-core-only performance;
- combined-model performance;
- held-out-period performance.

A result that looks strong only because all animal-headed controls are collapsed into one negative class is inadmissible.

## 3. Myth-source ledger

### 3.1 Osiris, not Ra, is the robust dismembered deity

The murder/dismemberment/restoration complex belongs to Osiris in the high-confidence source corpus. JANUS does not promote a narrative in which Ra is dismembered and Sobek gathers pieces of Ra.

### 3.2 Book of the Dead 113 / Coffin Text 158

The source-audited episode has Ra summon Sobek. Sobek searches/fishes and retrieves the hands/arms of Horus from the water with a snare/net. The text explicitly gives an aetiological explanation for the snare/net.

The same witness does **not** identify Seth as the amputator. The UCL translation introduces the episode as what Horus's mother did to him. Therefore `SETH_CUT_OFF_HORUS_HANDS_IN_BD113` is blocked.

### 3.3 Fourteen pieces is not a universal constant

The dismemberment of Osiris is robust. A fixed total of fourteen pieces is not treated as a universal pharaonic invariant. The famous fourteen-part count is especially prominent in the much later Plutarch tradition, while Egyptian ritual geographies and body-part traditions vary.

### 3.4 Sobek swallowing Osiris and losing his tongue

Retain only as **TEXTUALLY_UNCERTAIN**. A damaged Coffin Text 991 passage has been read in this direction, but the reading is disputed/conjectural. It must not be used as a canonical event in graph construction or training labels.

### 3.5 Eye of Horus / Wedjat

The robust level is:

- the Eye of Horus is injured/wounded in conflict traditions;
- it becomes whole/restored and carries healing/regenerative/protective force;
- it participates strongly in funerary and Osirian restoration contexts.

The exact mechanics differ across witnesses. JANUS therefore does not collapse all variants into one mandatory sequence such as `left lunar eye -> torn into N pieces -> Thoth alone reassembles -> single universal version`.

### 3.6 No default separate 'Eye of Osiris' iconographic class

Middle Kingdom coffin eye panels are repeatedly catalogued as Horus/wedjat eyes or magical eyes enabling the deceased to see the eastern sunrise. They must **not** be relabelled by default as a separate standard `EYE_OF_OSIRIS` class.

A phrase or object-specific Osirian association may still occur; that is different from asserting a stable parallel iconographic symbol with its own morphology.

## 4. Source hierarchy

**Tier A:** UCL Digital Egypt / Petrie Museum, Metropolitan Museum, British Museum, direct/catalogued ancient texts.

**Tier B:** ancient classical witnesses such as Plutarch, preserved as late witnesses and never silently projected backward as a universal pharaonic rule.

**Tier C:** modern blogs, tourism pages, social media, fandom, generic encyclopedic summaries. These may suggest search terms but do not promote claims.

## 5. Blind Sobek amendment

The v0.2 Sobek experiment now requires these negative classes before promotion:

- non-Sobek crocodiles;
- canid deities (Anubis, Wepwawet, Duamutef where eligible);
- non-Sobek crown/solar deities;
- falcon-headed deities;
- low-resolution/damaged/stylised animal heads.

Identity labels and museum descriptions remain hidden during feature extraction. The period holdout is frozen before unblinding. No retuning is allowed after labels are revealed.

## Claim ceiling

This protocol does **not** establish a direct Sobek–Wedjat lineage, an ancient hidden code, fraction mapping, or a universal mythic master narrative. It establishes a cleaner test environment in which crocodilian identity, canid confounds, contextual crown/solar features and text variants are kept separate.
