/*
 * components/results/LineItemsTable.jsx — renders invoice line items.
 *
 * The line_items array can be empty. We show this component only when
 * there are items to display.
 *
 * Each item: { description, quantity, unit_price, amount }
 * All fields are optional (the extractor may not find all of them).
 */
import { formatAmount } from "../../utils/formatters.js";

export default function LineItemsTable({ items = [], currency }) {
  if (!items || items.length === 0) return null;

  const hasQty   = items.some((i) => i.quantity != null);
  const hasPrice = items.some((i) => i.unit_price != null);
  const hasTotal = items.some((i) => i.amount != null);

  return (
    <div className="mt-6">
      <h3 className="section-heading">Line Items ({items.length})</h3>
      <div className="overflow-x-auto rounded-lg ring-1 ring-gray-200">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-2.5 font-medium text-gray-600 text-xs uppercase tracking-wide">
                Description
              </th>
              {hasQty   && <th className="text-right px-4 py-2.5 font-medium text-gray-600 text-xs uppercase tracking-wide">Qty</th>}
              {hasPrice && <th className="text-right px-4 py-2.5 font-medium text-gray-600 text-xs uppercase tracking-wide">Unit Price</th>}
              {hasTotal && <th className="text-right px-4 py-2.5 font-medium text-gray-600 text-xs uppercase tracking-wide">Amount</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {items.map((item, i) => (
              <tr key={i} className="hover:bg-gray-50/60 transition-colors">
                <td className="px-4 py-2.5 text-gray-900 max-w-xs">
                  {item.description || <span className="text-gray-400 italic">—</span>}
                </td>
                {hasQty   && <td className="px-4 py-2.5 text-right text-gray-700 tabular-nums">{item.quantity ?? "—"}</td>}
                {hasPrice && <td className="px-4 py-2.5 text-right text-gray-700 tabular-nums">{item.unit_price != null ? formatAmount(item.unit_price, currency) : "—"}</td>}
                {hasTotal && <td className="px-4 py-2.5 text-right font-medium text-gray-900 tabular-nums">{item.amount != null ? formatAmount(item.amount, currency) : "—"}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
