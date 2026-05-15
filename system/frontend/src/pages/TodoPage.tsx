import { useLocation } from "react-router-dom";

import { PageHeader } from "../components/common/PageHeader";
import { EmptyState, Section } from "../components/common/StateViews";

const todoTitles: Record<string, string> = {
  "/migration": "Review Targets",
  "/risk": "위험평가"
};

export function TodoPage() {
  const location = useLocation();
  const title = todoTitles[location.pathname] ?? "준비 중";

  return (
    <Section>
      <PageHeader title={title} eyebrow="준비 중" />
      <EmptyState title="준비 중" description="이 화면은 아직 구현 예정입니다." />
    </Section>
  );
}
