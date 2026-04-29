import { useId } from "react";

import { Button } from "../ui/button";
import { Dialog } from "../ui/dialog";

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  confirmVariant?: "primary" | "danger";
  pending?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  confirmVariant = "danger",
  pending = false,
  onCancel,
  onConfirm
}: ConfirmDialogProps) {
  const descriptionId = useId();
  return (
    <Dialog open={open} title={title} closeDisabled={pending} describedBy={descriptionId} onClose={onCancel}>
      <div className="section-stack">
        <p id={descriptionId} className="muted">{description}</p>
        <div className="form-actions">
          <Button type="button" variant="ghost" disabled={pending} onClick={onCancel}>
            취소
          </Button>
          <Button type="button" variant={confirmVariant} disabled={pending} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
