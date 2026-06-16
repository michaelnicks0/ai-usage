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
    "deepseek": "DeepSeek", "xai": "xAI", "openrouter": "OpenRouter",
    "vastai": "Vast.ai", "exa": "Exa", "x": "X API", "codex": "Codex",
    "claude": "Claude Code", "nous": "Nous", "google": "Google AI Studio",
}
TOKEN_PROVIDERS = {"deepseek", "xai"}
SUBSCRIPTION_PROVIDERS = {"codex", "claude", "google"}


def _provider_display(name: str | None) -> str:
    """Human-readable provider name, including account-qualified Codex rows."""
    if not name:
        return ""
    if name.startswith("codex:"):
        label = name.split(":", 1)[1]
        return f"Codex ({label})" if label else "Codex"
    return PROVIDER_DISPLAY.get(name, name)


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
    """Format time until reset for subscription quota display."""
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
        # Codex: subscription-only quota block
        if name == "codex":
            cx = d.extra
            if cx:
                entry = OrderedDict()
                accounts = cx.get("accounts")
                if accounts:
                    entry["accounts"] = accounts
                else:
                    entry["plan_type"] = cx.get("plan_type")
                    entry["session"] = cx.get("session")
                    entry["weekly"] = cx.get("weekly")
                sub_out["codex"] = entry
            continue

        # Token fields only for LLM providers
        if name in TOKEN_PROVIDERS:
            entry = _model_entry(d)
        else:
            entry = {}

        # Balance / spend (skip for Claude/Google — have no prepaid balance)
        if name not in ("claude", "google"):
            entry["balance"] = round(d.balance, 2) if d.balance is not None else None
            entry["period_spend"] = round(d.spent, 2) if d.spent is not None else None

        # Claude: rate-limit windows
        if name == "claude":
            cl = d.extra
            if cl:
                entry["plan_type"] = cl.get("plan_type")
                entry["session"] = cl.get("session")
                entry["weekly"] = cl.get("weekly")
            entry.pop("balance", None)
            entry.pop("period_spend", None)

        # Google: rate-limit quotas per model
        if name == "google":
            go = d.extra
            if go:
                entry["plan_type"] = go.get("plan_type")
                entry["models"] = go.get("models")
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
    token_labels = [
        "Tokens In (Hit)", "Tokens In (Miss)", "Tokens Out", "Tokens Total",
    ]

    # Separate API providers (table rows) from subscription providers (detail sections)
    table_results = {
        k: v for k, v in results.items() if k not in SUBSCRIPTION_PROVIDERS
    }
    # Preserve order from ALL_PROVIDERS
    ordered = []
    for name in registry.all_names():
        if name in table_results:
            ordered.append((name, table_results[name]))
    seen = {name for name, _ in ordered}
    ordered.extend((name, data) for name, data in table_results.items() if name not in seen)

    if not ordered:
        lines.append("")  # no table rows, go to detail sections
    else:
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

        display_names = [_provider_display(n) for n, _ in ordered]
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

    # ── Subscription Quotas table ──
    sub_rows = []
    
    # 1. Claude Code
    if "claude" in results and results["claude"].extra:
        cl = results["claude"].extra
        plan = cl.get("plan_type", "unknown").capitalize()
        sess = cl.get("session")
        weekly = cl.get("weekly")
        if sess:
            sub_rows.append((
                "Claude Code",
                plan,
                "Session",
                f"{sess['remaining_pct']}%",
                fmt_countdown(sess.get("resets_at"))
            ))
        if weekly:
            sub_rows.append((
                "Claude Code",
                plan,
                "Weekly",
                f"{weekly['remaining_pct']}%",
                fmt_countdown(weekly.get("resets_at"))
            ))
        if not sess and not weekly:
            reset_label = (
                "auth failed" if results["claude"].meta.get("oauth_error") else "unavailable"
            )
            sub_rows.append((
                "Claude Code",
                plan,
                "Rate Limits",
                "—",
                reset_label
            ))
            
    # 2. Codex
    if "codex" in results and results["codex"].extra:
        cx = results["codex"].extra
        accounts = cx.get("accounts")
        if accounts:
            iterable = accounts.items()
        else:
            iterable = [("", cx)]

        for label, acct in iterable:
            display = f"Codex ({label})" if label else "Codex"
            plan = acct.get("plan_type", "unknown").capitalize()
            sess = acct.get("session")
            if sess:
                sub_rows.append((
                    display,
                    plan,
                    "Session",
                    f"{sess['remaining_pct']}%",
                    fmt_countdown(sess.get("resets_at"))
                ))
            weekly = acct.get("weekly")
            if weekly:
                sub_rows.append((
                    display,
                    plan,
                    "Weekly",
                    f"{weekly['remaining_pct']}%",
                    fmt_countdown(weekly.get("resets_at"))
                ))
            if not sess and not weekly:
                reset_label = acct.get("error") or (
                    "auth failed" if results["codex"].meta.get("auth_error") else "unavailable"
                )
                sub_rows.append((
                    display,
                    plan,
                    "Rate Limits",
                    "—",
                    reset_label
                ))
            
    # 3. Google AI Studio
    if "google" in results and results["google"].extra:
        go = results["google"].extra
        plan = go.get("plan_type", "unknown")
        # Plan formatting
        if plan == "Ultra 20x":
            plan_str = "Ultra 20x"
        elif plan == "unknown":
            plan_str = "Unknown"
        else:
            plan_str = plan.capitalize()
            
        models_data = go.get("models", {})
        for mkey, mval in models_data.items():
            sub_rows.append((
                "Google AI Studio",
                plan_str,
                mval["display_name"],
                f"{mval['remaining_pct']}%",
                fmt_countdown(mval.get("resets_at"))
            ))
            
    if sub_rows:
        headers = ["Subscription", "Tier", "Resource", "Remaining", "Resets In"]
        
        # Compute column widths
        sub_w = max(len(r[0]) for r in [headers] + sub_rows)
        tier_w = max(len(r[1]) for r in [headers] + sub_rows)
        res_w = max(len(r[2]) for r in [headers] + sub_rows)
        rem_w = max(len(r[3]) for r in [headers] + sub_rows)
        rst_w = max(len(r[4]) for r in [headers] + sub_rows)
        
        lines.append("Subscription Quotas")
        lines.append(f"{headers[0]:<{sub_w}}  {headers[1]:<{tier_w}}  {headers[2]:<{res_w}}  {headers[3]:>{rem_w}}  {headers[4]:>{rst_w}}")
        lines.append(f"{'─' * sub_w}  {'─' * tier_w}  {'─' * res_w}  {'─' * rem_w}  {'─' * rst_w}")
        
        for r in sub_rows:
            lines.append(f"{r[0]:<{sub_w}}  {r[1]:<{tier_w}}  {r[2]:<{res_w}}  {r[3]:>{rem_w}}  {r[4]:>{rst_w}}")
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
        label = f" for {_provider_display(provider)}" if provider else ""
        lines.append(f"No history found{label}. Run ai-usage first to collect snapshots.")
        return "\n".join(lines)

    prefix = (
        f"History — {_provider_display(provider)}"
        if provider else "History — all providers"
    )
    lines.append(f"{prefix}  ({len(rows)} rows)\n")

    show_provider = (not provider) or any(r[1] != provider for r in rows)

    # Build columns
    cols = []
    for r in rows:
        ts, prov, bal, spd, inp, cached, outp = r
        ts_short = ts.replace("T", " ").split("+")[0].split("Z")[0][:16]
        total = (cached or 0) + (inp or 0) + (outp or 0)
        cols.append((ts_short, _provider_display(prov), bal, spd, cached or 0, inp or 0, outp or 0, total))

    headers = ["Timestamp", "Balance", "Spend", "In(Hit)", "In(Miss)", "Out", "Total"]
    if show_provider:
        headers.insert(1, "Provider")

    col_w = [len(h) for h in headers]
    for row in cols:
        ts_d, prov_n, bal, spd, cached, inp, outp, total = row
        vals = [ts_d, fmt_amt(bal), fmt_amt(spd),
                fmt_tok(cached), fmt_tok(inp), fmt_tok(outp), fmt_tok(total)]
        if show_provider:
            vals.insert(1, prov_n)
        for i, v in enumerate(vals):
            col_w[i] = max(col_w[i], len(v))

    lines.append("  ".join(h.center(col_w[i]) for i, h in enumerate(headers)))
    lines.append("─" * (sum(col_w) + 2 * (len(headers) - 1)))
    for row in cols:
        ts_d, prov_n, bal, spd, cached, inp, outp, total = row
        vals = [ts_d, fmt_amt(bal), fmt_amt(spd),
                fmt_tok(cached), fmt_tok(inp), fmt_tok(outp), fmt_tok(total)]
        if show_provider:
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
