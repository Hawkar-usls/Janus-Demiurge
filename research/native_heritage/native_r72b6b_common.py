from native_r72b6_common import *
# Witnesses are textual evidence of a statement, not external proof.
RX={
"event_denial":r"\b(?:not|never|yet to|failed to|unable to|could not|didn't|hasn't|wasn't|weren't)\s+(?:(?:be|been|being|actually|independently|successfully|ever)\s+){0,4}(?:perform\w*|conduct\w*|complet\w*|execut\w*|carr(?:y|ied)\s+out|r[au]n|test\w*|finish\w*|take\s+place|took\s+place|start\w*|launch\w*|initiat\w*|happen\w*|occur\w*)\b|\b(?:no|without)\s+(?:actual\s+)?(?:experiment|trial|survey|audit|run|measurement|test)\s+(?:was\s+)?(?:performed|conducted|completed|executed|started|took place)\b|\b(?:cancelled|canceled|called off|abandoned)\s+(?:before|prior to)\s+(?:execution|start|measurement|data collection)\b",
"event_uncertain":r"\b(?:whether|if)\b.{0,100}\b(?:uncertain|unknown|unclear|unconfirmed)\b|\b(?:uncertain|unknown|unclear|unconfirmed)\b.{0,100}\b(?:whether|if)\b|\b(?:may|might|could)\s+(?:have\s+)?(?:been\s+)?(?:performed|conducted|run|completed|executed|happened|taken place)\b",
"future":r"\b(?:will|shall|scheduled|planned|proposed|intends? to|is to be)\b|\b(?:future|next)\s+(?:trial|test|run|experiment|step|evaluation)\b|^[\"']?\s*(?:repeat|conduct|perform|run|evaluate|measure|test|obtain|compare|assess|collect|check)\b",
"completed":r"\b(?:performed|conducted|completed|executed|carried out|ran|finished|took place|was run|has run|was completed|went ahead|was undertaken|was concluded|took measurements)\b",
"negative":r"\b(?:no|zero|none|absence of|without)\s+(?:(?:statistically|significant|measurable|detectable|new|any|additional|reproducible|observable|meaningful)\s+){0,4}(?:difference\w*|effect\w*|gain\w*|improvement\w*|signal\w*|error\w*|mismatch\w*|change\w*|discrepanc\w*|anomal\w*|shift\w*|deviation\w*|increase\w*|reduction\w*|advantage\w*|correlation\w*|echo\w*|excess\w*|response\w*|bias\w*|peak\w*|variation\w*)\b|\b(?:did not|failed to|could not|never)\s+(?:find|detect|observe|measure|show|identify|produce|reveal|register|see)\b",
"observation":r"\b(?:found|detected|observed|measured|showed|reported|yielded|returned|recorded|revealed|identified|produced|registered|saw|confirmed|reproduced|matched|agreed|verified|find|detect|observe|identify|show|see)\b",
"mixed":r"\b(?:but|however|although|yet|whereas|while)\b.{0,140}\b(?:not|no|cannot|unable|lack|insufficient|unproven)\b.{0,85}\b(?:external|independent|physical|causal|scientific|generaliz\w*|broader|validity|provenance)\b|\b(?:but|however|although|yet|whereas|while)\b.{0,140}\b(?:external|independent|physical|causal|scientific|generaliz\w*|broader|validity|provenance)\b.{0,85}\b(?:not|no|cannot|unable|lack|insufficient|unproven)\b",
"unknown_outcome":r"\b(?:inconclusive|undetermined|uninterpretable|unknown|ambiguous|unavailable|unresolved|cannot tell)\b|\b(?:no|without)\s+(?:usable|valid|interpretable)\s+(?:data|results?|measurements?)\b",
"modal_outcome":r"\b(?:may|might|possibly|potentially|could)\s+(?:indicate|suggest|show|reflect|represent|mean)\b",
"other":r"^[\"']?\s*(?:identifier|title|record name|document caption|reference number|catalogue entry|metadata label)\b",
"multiple":r"\b(?:another|a second|a separate|the second|the earlier|the previous|the first|the original|the later)\s+(?:trial|test|run|experiment|audit|survey)\b"
}
def witnesses(row):
    try:v=json.loads(row["value"])
    except Exception:return "",{}
    if not isinstance(v,str):return "",{}
    out={}
    for name,rx in RX.items():
        m=list(re.finditer(rx,v,re.I))
        if m:out[name]=[{"start":x.start(),"end":x.end(),"text":x.group()} for x in m]
    return v,out
def locked_scope(row,e,o):
    v,w=witnesses(row);has=lambda k:k in w
    # Every override requires explicit matched text. Multi-event ambiguity abstains.
    if has("other"):return 4,4,"metadata",w
    if has("multiple") and (has("event_denial") or has("future")) and has("completed"):
        return -1,-1,"multiple_events",w
    if has("event_uncertain"):return 3,2,"uncertain_execution",w
    if has("event_denial"):return 1,2,"negated_execution",w
    if has("future"):
        # Past and future events in the same sentence are not collapsed.
        if has("completed") and re.search(r"\b(?:but|and|while|however)\b",v,re.I):return -1,-1,"mixed_time",w
        return 2,2,"planned_execution",w
    if has("completed") and has("mixed"):return 0,3,"limited_scope",w
    if has("completed") and (has("unknown_outcome") or has("modal_outcome")):return 0,2,"unknown_outcome",w
    if has("completed") and has("negative") and has("observation"):return 0,1,"observed_negative",w
    if has("completed") and has("observation") and not has("negative"):return 0,0,"observed_positive",w
    # No verified textual witness for a claimed outcome: never accept evidence from neural score alone.
    if e==0 and o in (0,1):return -1,-1,"missing_execution_or_outcome_witness",w
    return e,o,"neural_fallback",w
def fresh_cases():
    # New manually authored wording; no reuse of B6 exam statements.
    items=[
      ("Following the radio receiver audit, which was undertaken yesterday, investigators identified no detectable excess.",0,1,"negative_result"),
      ("The toxicity assay was conducted; no measurable response was recorded.",0,1,"negative_result"),
      ("After the pressure test went ahead, the instruments did not register a deviation.",0,1,"negative_result"),
      ("The spectral comparison finished and revealed zero new peaks.",0,1,"negative_result"),
      ("No meaningful variation was observed after the calibration was concluded.",0,1,"negative_result"),
      ("The pulse experiment was executed; the team failed to detect a correlation.",0,1,"negative_result"),
      ("The migration test was carried out and found no additional errors.",0,1,"negative_result"),
      ("The diffraction trial took place and the sensors recorded no significant change.",0,1,"negative_result"),
      ("Investigators had not actually launched the impedance test, and its output is unknown.",1,2,"negated_execution"),
      ("The observation campaign was never initiated; the result is unavailable.",1,2,"negated_execution"),
      ("The laboratory team didn't carry out the viscosity assay.",1,2,"negated_execution"),
      ("The field trial was called off before data collection.",1,2,"negated_execution"),
      ("The probe test has yet to be started; no findings are available.",1,2,"negated_execution"),
      ("No experiment was conducted on the replacement sensor.",1,2,"negated_execution"),
      ("The team failed to perform the stress test; no output exists.",1,2,"negated_execution"),
      ("The second-stage scan was not actually executed.",1,2,"negated_execution"),
      ("The conductivity measurement was undertaken and confirmed a positive response.",0,0,"positive"),
      ("The retention trial went ahead and recorded a measurable gain.",0,0,"positive"),
      ("The noise benchmark was concluded and the readings matched the reference.",0,0,"positive"),
      ("The particle assay was executed and revealed a new peak.",0,0,"positive"),
      ("The ground calibration finished and verified the reference values.",0,0,"positive"),
      ("The optical test was carried out and reproduced the earlier result.",0,0,"positive"),
      ("The survey is scheduled for Monday to assess the instrument drift.",2,2,"future"),
      ("Conduct the next comparison using independent samples.",2,2,"future"),
      ("The team will undertake a detector test after maintenance.",2,2,"future"),
      ("A future trial is proposed to check the preliminary observation.",2,2,"future"),
      ("Repeat the thermal assay with a new control group.",2,2,"future"),
      ("The verification run is planned for the next review.",2,2,"future"),
      ("It remains unclear whether the electrical test took place.",3,2,"uncertainty"),
      ("The calibration might have been completed; no trace is available.",3,2,"uncertainty"),
      ("Whether the recovery exercise happened is unconfirmed.",3,2,"uncertainty"),
      ("The survey may have been performed, but records are missing.",3,2,"uncertainty"),
      ("The replication was conducted but its result was inconclusive.",0,2,"completed_unknown"),
      ("The sensor audit was completed; no usable measurements were returned.",0,2,"completed_unknown"),
      ("The field test finished, but the observed outcome is ambiguous.",0,2,"completed_unknown"),
      ("The comparison was executed; the result remains undetermined.",0,2,"completed_unknown"),
      ("The benchmark was performed and confirmed local agreement, but external validity was not established.",0,3,"mixed_scope"),
      ("The trial was completed and matched internal records; however, independent provenance remains unproven.",0,3,"mixed_scope"),
      ("The replay was conducted and reproduced the checksum, but cannot establish a physical effect.",0,3,"mixed_scope"),
      ("The audit finished and verified the internal log, but the broader causal claim is not supported.",0,3,"mixed_scope"),
      ("Catalogue entry for the sensor-validation protocol.",4,4,"other"),
      ("Reference number of the completed test manifest: 872.",4,4,"other"),
      ("Metadata label for the experimental series.",4,4,"other"),
      ("Document caption: receiver assessment.",4,4,"other")
    ]
    rows=[]
    for i,(v,e,o,c) in enumerate(items):
        g=int(compose(torch.tensor([e]),torch.tensor([o]))[0])
        for j,path in enumerate((["record","statement"],["audit","note"])):
            rows.append({"source":"fresh_authored","path":path,"type":"string","value":json.dumps(v),"label":GROUP_NAMES[g],"event":e,"outcome":o,"cohort":c,"family":str(i),"contrast_id":f"{i}:{j}"})
    return rows
