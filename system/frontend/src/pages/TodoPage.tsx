import { useLocation } from "react-router-dom";

import { PageHeader } from "../components/common/PageHeader";
import { EmptyState, Section } from "../components/common/StateViews";

const todoTitles: Record<string, string> = {
  "/migration": "마이그레이션",
  "/risk": "위험평가"
};

export function TodoPage() {
  const location = useLocation();
  const title = todoTitles[location.pathname] ?? "TODO";

  return (
    <Section>
      <PageHeader title={title} eyebrow="TODO" />
      <EmptyState title="TODO" description="이 화면은 아직 구현 예정입니다." />
    </Section>
  );
}
