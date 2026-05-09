import { Navigate } from "react-router-dom";

import { PageHeader } from "../components/common/PageHeader";
import { EmptyState, ErrorState, LoadingState, Section } from "../components/common/StateViews";
import { useSelectedSnapshot } from "../features/snapshots/useSelectedSnapshot";

export function PerformancePage() {
  const { snapshots, selectedSnapshotId } = useSelectedSnapshot();

  if (snapshots.isLoading) {
    return <LoadingState />;
  }
  if (snapshots.isError) {
    return (
      <Section>
        <PageHeader title="가용성 검사" />
        <ErrorState error={snapshots.error} onRetry={() => void snapshots.refetch()} />
      </Section>
    );
  }
  if (!selectedSnapshotId) {
    return (
      <Section>
        <PageHeader title="가용성 검사" />
        <EmptyState title="스냅샷이 없습니다" description="스캔을 실행해 자산 스냅샷을 생성한 뒤 가용성 검사 결과를 확인할 수 있습니다." />
      </Section>
    );
  }
  return <Navigate to={`/snapshots/${selectedSnapshotId}/performance`} replace />;
}
