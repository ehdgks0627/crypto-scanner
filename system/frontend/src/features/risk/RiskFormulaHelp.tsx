import type { RiskWeightsInput } from "../../api/types";

export function riskWeightLabel(key: keyof RiskWeightsInput) {
  const labels: Record<keyof RiskWeightsInput, string> = {
    wA: "A 가중치",
    wD: "D 가중치",
    wE: "E 가중치",
    wL: "L 가중치",
    wC: "C 가중치"
  };
  return labels[key];
}

export function RiskFormulaHelp() {
  return (
    <div className="callout risk-formula-help" aria-label="위험 점수 계산식">
      <strong className="risk-formula-help__title">위험 점수 계산식</strong>
      <p className="mono risk-formula-help__formula">점수 = round(100 × A' × avg(D', E', L', C'))</p>
      <p className="muted risk-formula-help__note">각 계수는 0.5를 기준으로 가중치를 적용합니다. 예: A' = clamp(0.5 + (A - 0.5) × wA).</p>
      <p className="muted risk-formula-help__note">계산 결과는 0~100으로 제한하며, 등급은 치명 80 이상, 높음 60 이상, 보통 30 이상, 낮음 30 미만입니다.</p>
      <dl className="detail-list">
        <div>
          <dt>A</dt>
          <dd>알고리즘 위험 계수</dd>
        </div>
        <div>
          <dt>D</dt>
          <dd>데이터 민감도 계수</dd>
        </div>
        <div>
          <dt>E</dt>
          <dd>노출 범위 계수</dd>
        </div>
        <div>
          <dt>L</dt>
          <dd>보호 기간 계수</dd>
        </div>
        <div>
          <dt>C</dt>
          <dd>중요도 계수</dd>
        </div>
        <div>
          <dt>w</dt>
          <dd>가중치 1은 그대로, 1 초과는 강화, 1 미만은 완화</dd>
        </div>
      </dl>
    </div>
  );
}
