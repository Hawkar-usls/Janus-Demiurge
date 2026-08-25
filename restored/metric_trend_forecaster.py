from __future__ import annotations
import hashlib, json, math
from typing import Any

SCHEMA="janus.metric_trend_forecast.v1"


def _canon(value:Any)->bytes:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")


def _finite(name:str,value:Any)->float:
    if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
    return float(value)


class MetricTrendForecaster:
    def __init__(self, lead_factor:float=1.8):
        self.lead_factor=_finite("lead_factor",lead_factor)
        self.prev_score=None
        self.prev_prev_score=None
        self.prev_aux=None

    def step(self, score:float, aux_metric:float)->dict[str,Any]:
        score=_finite("score",score); aux=_finite("aux_metric",aux_metric)
        if self.prev_score is None:
            velocity=0.0; acceleration=0.0; predicted_score=score; predicted_aux=aux; phase="WARMUP"
        else:
            velocity=score-self.prev_score
            acceleration=score-2.0*self.prev_score+self.prev_prev_score
            predicted_score=score+velocity*self.lead_factor+0.5*acceleration
            predicted_aux=aux+(aux-self.prev_aux)*self.lead_factor
            phase="FORECAST"
        self.prev_prev_score=score if self.prev_score is None else self.prev_score
        self.prev_score=score; self.prev_aux=aux
        body={
          "schema":SCHEMA,"phase":phase,"score":score,"aux_metric":aux,
          "velocity":velocity,"acceleration":acceleration,
          "predicted_score":predicted_score,"predicted_aux_metric":predicted_aux,
          "lead_factor":self.lead_factor,
          "authority":{"changes_runtime":False,"chooses_action":False,"claims_future_information":False},
          "laws":["TREND_EXTRAPOLATION_NE_PRECOGNITION","FORECAST_NE_CAUSAL_EVIDENCE","FORECAST_MUST_BE_SCORED_AGAINST_REALIZED_OUTCOME"]
        }
        body["forecast_sha256"]=hashlib.sha256(_canon(body)).hexdigest()
        return body
