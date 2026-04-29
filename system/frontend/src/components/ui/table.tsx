import type { ReactNode } from "react";

export type TableColumn<T> = {
  key: string;
  header: ReactNode;
  render: (item: T) => ReactNode;
  align?: "left" | "right" | "center";
};

type DataTableProps<T> = {
  columns: TableColumn<T>[];
  items: T[];
  getRowKey: (item: T, index: number) => string | number;
  empty?: ReactNode;
};

export function DataTable<T>({ columns, items, getRowKey, empty }: DataTableProps<T>) {
  if (items.length === 0) {
    return <div className="ui-table__empty">{empty ?? "데이터가 없습니다."}</div>;
  }

  return (
    <div className="ui-table-wrap">
      <table className="ui-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} className={column.align ? `is-${column.align}` : undefined}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => (
            <tr key={getRowKey(item, index)}>
              {columns.map((column) => (
                <td key={column.key} className={column.align ? `is-${column.align}` : undefined}>
                  {column.render(item)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
