"""Rendering: table and JSON output formats."""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Callable

from ai_usage.models import ProviderData
from ai_usage.providers import registry

# ── Constants ──

PROVIDER_DISPLAY = {
    "deepseek": "DeepSeek", "xai": "xAI", "vastai": "Vast.ai",
    "exa": "Exa", "x": "X API", "codex": "Codex",
    "claude": "Claude Code", "nous": "Nous",
}

TOKEN_PROVIDERS = {"deepseek", "xai"}
SUBSCRIPTION_PROVIDERS = {"codex", "claude"}

# ── Formatting helpers ──


def fmt_amt(n: float | None) -> str:
    if n is None:
        return "     —"
    return f"${n:,.2f}"


def fmt_tok(n: int) -> str:
    if n == 0:
        return "        —"
    return f"{n:>9,}"


def fmt_countdown(ts: int | None) -> str:
    """Format time until reset for Codex/Claude display."""
    if ts is None:
        return "—"
    delta = datetime.fromtimestamp(ts, tz=timezone.utc) - datetime.now(timezone.utc)
    if delta.total_seconds() <= 0:
        return "now"
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    mins = rem // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins or not parts:
        parts.append(f"{mins}m")
    return "".join(parts)


def _fmt_renewal(ts: int | None) -> str:
    """Format a renewal countdown with spaces, matching Nous style.

    Returns empty string if ts is None or already passed.
    """
    if ts is None:
        return ""
    delta = datetime.fromtimestamp(ts, tz=timezone.utc) - datetime.now(timezone.utc)
    if delta.total_seconds() <= 0:
        return ""
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    mins = rem // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or parts:
        parts.append(f"{hours}h")
    if mins or not parts:
        parts.append(f"{mins}m")
    return " ".join(parts)


def _token_pcts(d: ProviderData) -> tuple[float, float]:
    total_in = d.tokens.cached + d.tokens.input
    if total_in > 0:
        hit = round(d.tokens.cached / total_in * 100, 1)
        miss = round(d.tokens.input / total_in * 100, 1)
        return hit, miss
    return 0.0, 0.0


def _model_entry(d: ProviderData) -> dict[str, Any]:
    hit, miss = _token_pcts(d)
    return {
        "tokens_in_hit": d.tokens.cached,
        "tokens_in_hit_percentage": hit,
        "tokens_in_miss": d.tokens.input,
        "tokens_in_miss_percentage": miss,
        "tokens_out": d.tokens.output,
        "tokens_total": d.tokens.total,
    }


# ── JSON renderer ──


def render_json(
    results: dict[str, ProviderData],
    show_model: bool = False,
) -> str:
    """Render results as JSON string."""
    api_out: OrderedDict = OrderedDict()
    sub_out: OrderedDict = OrderedDict()

    for name, d in results.items():
        # Codex: only the codex block
        if name == "codex":
            cx = d.extra
            if cx:
                entry_cx: dict = {
                    "plan_type": cx.get("plan_type"),
                    "session": cx.get("session"),
                    "weekly": cx.get("weekly"),
                }
                # Add renews_in to session and weekly
                for window_key in ("session", "weekly"):
                    win = entry_cx.get(window_key)
                    if win and win.get("resets_at"):
                        win["renews_in"] = _fmt_renewal(win["resets_at"])
                sub_out["codex"] = entry_cx
            continue

        # Token fields only for LLM providers
        if name in TOKEN_PROVIDERS:
            entry = _model_entry(d)
        else:
            entry = {}

        # Balance / spend (skip for Claude — has no prepaid balance)
        if name != "claude":
            entry["balance"] = round(d.balance, 2) if d.balance is not None else None
            entry["period_spend"] = round(d.spent, 2) if d.spent is not None else None

        # Claude: rate-limit windows
        if name == "claude":
            cl = d.extra
            if cl:
                entry["plan_type"] = cl.get("plan_type")
                entry["session"] = cl.get("session")
                entry["weekly"] = cl.get("weekly")
                # Add renews_in
                for window_key in ("session", "weekly"):
                    win = entry.get(window_key)
                    if win and win.get("resets_at"):
                        win["renews_in"] = _fmt_renewal(win["resets_at"])
            entry.pop("balance", None)
            entry.pop("period_spend", None)

        # Nous: subscription details
        if name == "nous":
            nx = d.extra
            if nx:
                entry["plan_type"] = nx.get("plan_type")
                entry["monthly_charge"] = nx.get("monthly_charge")
                entry["credits_remaining"] = nx.get("credits_remaining")
                entry["current_period_end"] = nx.get("current_period_end")
                # Compute renews_in from period end
                pe = nx.get("current_period_end")
                if pe:
                    try:
                        dt = datetime.fromisoformat(pe.replace("Z", "+00:00"))
                        entry["renews_in"] = _fmt_renewal(int(dt.timestamp()))
                    except Exception:
                        pass

        if show_model and d.models:
            entry["models"] = OrderedDict()
            for mname, md in d.models.items():
                if name == "claude":
                    entry["models"][mname] = {
                        "input_tokens": md.input,
                        "cached_tokens": md.cached,
                        "output_tokens": md.output,
                        "total_tokens": md.total,
                    }
                else:
                    # Create a synthetic ProviderData-like for _model_entry
                    class _M:
                        tokens = md
                    entry["models"][mname] = {
                        "tokens_in_hit": md.cached,
                        "tokens_in_hit_percentage": md.hit_pct,
                        "tokens_in_miss": md.input,
                        "tokens_in_miss_percentage": md.miss_pct,
                        "tokens_out": md.output,
                        "tokens_total": md.total,
                    }

        if name in SUBSCRIPTION_PROVIDERS:
            sub_out[PROVIDER_DISPLAY[name].lower()] = entry
        else:
            api_out[PROVIDER_DISPLAY[name].lower()] = entry

    out = OrderedDict()
    if api_out:
        out["api"] = api_out
    if sub_out:
        out["subscription"] = sub_out
    return json.dumps(out, indent=2)


# ── Table renderer ──


def render_table(
    results: dict[str, ProviderData],
    show_model: bool = False,
) -> str:
    """Render results as a formatted table (returns string for testability)."""
    lines: list[str] = []

    # Separate API providers (table rows) from subscription providers (detail sections)
    table_results = {
        k: v for k, v in results.items() if k not in SUBSCRIPTION_PROVIDERS
    }
    # Preserve order from ALL_PROVIDERS
    ordered = []
    for name in registry.all_names():
        if name in table_results:
            ordered.append((name, table_results[name]))

    if not ordered:
        lines.append("")  # no table rows, go to detail sections
    else:
        token_labels = [
            "Tokens In (Hit)", "Tokens In (Miss)", "Tokens Out", "Tokens Total",
        ]

        def _fmt_bal(d: ProviderData) -> str:
            if d.extra and d.extra.get("credits"):
                bal = d.extra["credits"].get("balance", "0")
                return f"{bal} credits".rjust(10) if len(f"{bal} credits") <= 10 else f"{bal} credits"
            return fmt_amt(d.balance)

        def _fmt_spend(d: ProviderData) -> str:
            if d.extra:
                sess = d.extra.get("session")
                if sess:
                    pct = sess["remaining_pct"]
                    cd = fmt_countdown(sess.get("resets_at"))
                    return f"{pct}% · {cd}".rjust(12)
            return fmt_amt(d.spent)

        provider_col = "Provider"
        stat_headers = ["Balance", "Spend"] + token_labels
        stat_fns: list[Callable] = [
            _fmt_bal,
            _fmt_spend,
            lambda d: fmt_tok(d.tokens.cached),
            lambda d: fmt_tok(d.tokens.input),
            lambda d: fmt_tok(d.tokens.output),
            lambda d: fmt_tok(d.tokens.total),
        ]

        display_names = [PROVIDER_DISPLAY[n] for n, _ in ordered]
        table_data = [d for _, d in ordered]

        name_w = max(max(len(n) for n in display_names), len(provider_col))
        col_w = [len(h) for h in stat_headers]
        for ci, fn in enumerate(stat_fns):
            for d in table_data:
                col_w[ci] = max(col_w[ci], len(fn(d)))

        # Header
        lines.append(
            f"{provider_col:>{name_w}}  " +
            "  ".join(h.center(col_w[i]) for i, h in enumerate(stat_headers))
        )
        lines.append(f"{'─' * name_w}──" + "──".join("─" * w for w in col_w))

        # Data rows
        for i, pname in enumerate(display_names):
            vals = [fn(table_data[i]) for fn in stat_fns]
            line = "  ".join(v.rjust(col_w[j]) for j, v in enumerate(vals))
            lines.append(f"{pname:>{name_w}}  {line}")

        lines.append("")

    # ── Codex detail section ──
    if "codex" in results and results["codex"].extra:
        cx = results["codex"].extra
        lines.append(f"Codex Details  ({cx.get('plan_type', 'unknown')})")
        lines.append("─" * 48)
        sess = cx.get("session")
        if sess:
            pct = sess["remaining_pct"]
            bar_w = 30
            filled = int(bar_w * pct / 100)
            bar = "█" * filled + "░" * (bar_w - filled)
            lines.append(f"  Session      {pct}% remaining  [{bar}]")
            lines.append(f"               Resets in {fmt_countdown(sess.get('resets_at'))}")
        weekly = cx.get("weekly")
        if weekly:
            pct = weekly["remaining_pct"]
            bar_w = 30
            filled = int(bar_w * pct / 100)
            bar = "█" * filled + "░" * (bar_w - filled)
            lines.append(f"  Weekly       {pct}% remaining  [{bar}]")
            cd = _fmt_renewal(weekly.get("resets_at"))
            if cd:
                lines.append(f"               Renews in {cd}")
        lines.append("")

    # ── Claude detail section ──
    if "claude" in results and results["claude"].extra:
        cl = results["claude"].extra
        lines.append(f"Claude Code Details  ({cl.get('plan_type', 'unknown')})")
        lines.append("─" * 48)
        sess = cl.get("session")
        if sess:
            pct = sess["remaining_pct"]
            bar_w = 30
            filled = int(bar_w * pct / 100)
            bar = "█" * filled + "░" * (bar_w - filled)
            lines.append(f"  Session      {pct}% remaining  [{bar}]")
            lines.append(f"               Resets in {fmt_countdown(sess.get('resets_at'))}")
        weekly = cl.get("weekly")
        if weekly:
            pct = weekly["remaining_pct"]
            bar_w = 30
            filled = int(bar_w * pct / 100)
            bar = "█" * filled + "░" * (bar_w - filled)
            lines.append(f"  Weekly       {pct}% remaining  [{bar}]")
            cd = _fmt_renewal(weekly.get("resets_at"))
            if cd:
                lines.append(f"               Renews in {cd}")
        lines.append("")

    # ── Nous detail section ──
    if "nous" in results and results["nous"].extra:
        nx = results["nous"].extra
        lines.append(f"Nous Details  ({nx.get('plan_type', 'unknown')})")
        lines.append("─" * 48)
        cr = nx.get("credits_remaining")
        if cr is not None:
            lines.append(f"  Subscription credits  ${cr:,.2f} remaining")
        mc = nx.get("monthly_charge")
        if mc is not None:
            lines.append(f"  Monthly charge        ${mc:,.2f}")
        pe = nx.get("current_period_end")
        if pe:
            try:
                dt = datetime.fromisoformat(pe.replace("Z", "+00:00"))
                ts = int(dt.timestamp())
                cd = _fmt_renewal(ts)
                if cd:
                    lines.append(f"  Renews in             {cd}")
            except Exception:
                pass
        lines.append("")

    # ── Per-model section ──
    if show_model:
        model_headers = token_labels
        model_fns: list[Callable] = [
            lambda d: fmt_tok(d.cached),
            lambda d: fmt_tok(d.input),
            lambda d: fmt_tok(d.output),
            lambda d: fmt_tok(d.total),
        ]

        for name, d in ordered:
            if not d.models:
                continue
            lines.append(f"Models — {PROVIDER_DISPLAY[name]}")
            mnames = list(d.models.keys())
            mdata = [d.models[m] for m in mnames]

            mname_w = max(max(len(n) for n in mnames), 5)
            mcol_w = [len(h) for h in model_headers]
            for ci, fn in enumerate(model_fns):
                for md in mdata:
                    mcol_w[ci] = max(mcol_w[ci], len(fn(md)))

            lines.append(
                f"{'':>{mname_w}}  " +
                "  ".join(h.center(mcol_w[i]) for i, h in enumerate(model_headers))
            )
            lines.append(f"{'─' * mname_w}──" + "──".join("─" * w for w in mcol_w))
            for mi, mname in enumerate(mnames):
                vals = [fn(mdata[mi]) for fn in model_fns]
                line = "  ".join(v.rjust(mcol_w[j]) for j, v in enumerate(vals))
                lines.append(f"{mname:>{mname_w}}  {line}")
            lines.append("")

    return "\n".join(lines)


# ── History rendering ──


def render_history(
    rows: list[tuple],
    provider: str | None = None,
) -> str:
    """Render history rows as a table string."""
    lines: list[str] = []

    if not rows:
        label = f" for {PROVIDER_DISPLAY.get(provider, provider)}" if provider else ""
        lines.append(f"No history found{label}. Run ai-usage first to collect snapshots.")
        return "\n".join(lines)

    prefix = (
        f"History — {PROVIDER_DISPLAY.get(provider, provider)}"
        if provider else "History — all providers"
    )
    lines.append(f"{prefix}  ({len(rows)} rows)\n")

    # Build columns
    cols = []
    for r in rows:
        ts, prov, bal, spd, inp, cached, outp = r
        ts_short = ts.replace("T", " ").split("+")[0].split("Z")[0][:16]
        total = (cached or 0) + (inp or 0) + (outp or 0)
        cols.append((ts_short, prov, bal, spd, cached or 0, inp or 0, outp or 0, total))

    headers = ["Timestamp", "Balance", "Spend", "In(Hit)", "In(Miss)", "Out", "Total"]
    if not provider:
        headers.insert(1, "Provider")

    col_w = [len(h) for h in headers]
    for row in cols:
        ts_d, prov_n, bal, spd, cached, inp, outp, total = row
        vals = [ts_d, fmt_amt(bal), fmt_amt(spd),
                fmt_tok(cached), fmt_tok(inp), fmt_tok(outp), fmt_tok(total)]
        if not provider:
            vals.insert(1, prov_n)
        for i, v in enumerate(vals):
            col_w[i] = max(col_w[i], len(v))

    lines.append("  ".join(h.center(col_w[i]) for i, h in enumerate(headers)))
    lines.append("─" * (sum(col_w) + 2 * (len(headers) - 1)))
    for row in cols:
        ts_d, prov_n, bal, spd, cached, inp, outp, total = row
        vals = [ts_d, fmt_amt(bal), fmt_amt(spd),
                fmt_tok(cached), fmt_tok(inp), fmt_tok(outp), fmt_tok(total)]
        if not provider:
            vals.insert(1, prov_n)
        line = "  ".join(v.rjust(col_w[i]) for i, v in enumerate(vals))
        lines.append(line)
    lines.append("")

    return "\n".join(lines)


def render_history_json(rows: list[tuple]) -> str:
    """Render history rows as JSON string."""
    out = []
    for r in rows:
        ts, prov, bal, spd, inp, cached, outp = r
        out.append({
            "timestamp": ts,
            "provider": prov,
            "balance": round(bal, 2) if bal is not None else None,
            "spend": round(spd, 2) if spd is not None else None,
            "tokens_cached": cached or 0,
            "tokens_input": inp or 0,
            "tokens_output": outp or 0,
        })
    return json.dumps(out, indent=2)
