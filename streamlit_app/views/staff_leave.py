"""Leave requests, approvals, and substitute coverage."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import streamlit as st

from http_api import api_request


def _me_teacher() -> Optional[Dict[str, Any]]:
    r = api_request("GET", "/me/teacher")
    if r.status_code == 404:
        return None
    if not r.is_success:
        st.error(r.text)
        return None
    return r.json()


def _is_approver() -> bool:
    r = api_request("GET", "/staff/leave-approvers/me")
    if not r.is_success:
        return False
    data = r.json()
    return bool(data.get("is_leave_approver"))


def _teacher_name_map() -> Dict[str, str]:
    r = api_request("GET", "/directory/educators")
    if not r.is_success or not isinstance(r.json(), list):
        return {}
    return {str(t["id"]): str(t.get("full_name", "—")) for t in r.json()}


def render() -> None:
    st.header("Leave, approvals & substitute coverage")
    st.caption(
        "Submit absence requests, route them through designated approvers, and coordinate "
        "daily substitute coverage. Access follows your Supabase row-level security policies."
    )

    approver = _is_approver()
    if approver:
        st.success("You are registered as a **leave approver** for this organization.")
    else:
        st.info(
            "**Approvers:** add your account to `leave_approvers`, or ask a **platform administrator** "
            "(see `platform_admins` in Supabase) to approve requests. Staff may always submit and "
            "withdraw their own pending requests."
        )

    me = _me_teacher()
    names = _teacher_name_map()

    st.divider()
    st.subheader("Request time away")
    if not me:
        st.warning("Create your educator profile under **Overview & roster** before requesting leave.")
    else:
        st.caption(f"Requesting as **{me.get('full_name', '')}**.")
        with st.form("leave_request_form"):
            lt = st.selectbox(
                "Leave type",
                ["vacation", "sick", "personal", "professional", "family", "other"],
            )
            c1, c2 = st.columns(2)
            with c1:
                sd = st.date_input("First day out", value=date.today(), key="lr_sd")
            with c2:
                ed = st.date_input("Last day out", value=date.today(), key="lr_ed")
            half = st.checkbox("Half-day request", value=False)
            reason = st.text_area("Context for your supervisor (optional)", height=80)
            if st.form_submit_button("Submit leave request"):
                cr = api_request(
                    "POST",
                    "/staff/leave-requests",
                    json={
                        "teacher_id": me["id"],
                        "request_type": lt,
                        "start_date": sd.isoformat(),
                        "end_date": ed.isoformat(),
                        "is_half_day": half,
                        "reason": reason.strip() or None,
                    },
                )
                if cr.is_success:
                    st.success("Request submitted for approval.")
                    st.session_state.pop("_leave_cache", None)
                else:
                    st.error(cr.text)

    st.divider()
    st.subheader("My leave requests")
    if st.button("Refresh leave list", key="lr_refresh"):
        st.session_state.pop("_leave_cache", None)
    if "_leave_cache" not in st.session_state:
        lr = api_request("GET", "/staff/leave-requests")
        st.session_state["_leave_cache"] = lr.json() if lr.is_success else []
        if not lr.is_success:
            st.error(lr.text)
    rows: List[Dict[str, Any]] = list(st.session_state.get("_leave_cache") or [])
    own_id = me["id"] if me else None
    mine = [x for x in rows if own_id and str(x.get("teacher_id")) == str(own_id)]
    if not mine:
        st.caption("No requests on file for your profile.")
    for req in mine:
        with st.expander(
            f"{req.get('start_date', '')} → {req.get('end_date', '')} · "
            f"{req.get('request_type', '')} · **{req.get('status', '')}**"
        ):
            st.write("**Reason:**", req.get("reason") or "—")
            st.write("**Half-day:**", "Yes" if req.get("is_half_day") else "No")
            if req.get("review_notes"):
                st.write("**Approver notes:**", req.get("review_notes"))
            if req.get("status") == "pending":
                if st.button("Withdraw request", key=f"lr_del_{req['id']}"):
                    dr = api_request("DELETE", f"/staff/leave-requests/{req['id']}")
                    if dr.is_success:
                        st.success("Withdrawn.")
                        st.session_state.pop("_leave_cache", None)
                        st.rerun()
                    else:
                        st.error(dr.text)

    if approver:
        st.divider()
        st.subheader("Approval queue")
        pending = [x for x in rows if x.get("status") == "pending"]
        if not pending:
            st.caption("No pending requests in your visibility scope.")
        for req in pending:
            tid = str(req.get("teacher_id", ""))
            who = names.get(tid, "Educator")
            with st.expander(f"Pending · {who} · {req.get('start_date')} → {req.get('end_date')}"):
                st.write("**Type:**", req.get("request_type"))
                st.write("**Reason:**", req.get("reason") or "—")
                notes = st.text_input("Decision notes (optional)", key=f"ap_note_{req['id']}")
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("Approve", key=f"ap_ok_{req['id']}"):
                        pr = api_request(
                            "PATCH",
                            f"/staff/leave-requests/{req['id']}",
                            json={"status": "approved", "review_notes": notes or None},
                        )
                        if pr.is_success:
                            st.success("Approved.")
                            st.session_state.pop("_leave_cache", None)
                            st.rerun()
                        else:
                            st.error(pr.text)
                with c2:
                    if st.button("Deny", key=f"ap_no_{req['id']}"):
                        pr = api_request(
                            "PATCH",
                            f"/staff/leave-requests/{req['id']}",
                            json={"status": "denied", "review_notes": notes or None},
                        )
                        if pr.is_success:
                            st.success("Recorded as denied.")
                            st.session_state.pop("_leave_cache", None)
                            st.rerun()
                        else:
                            st.error(pr.text)
                with c3:
                    st.caption("Decisions are stamped with your account.")

    st.divider()
    st.subheader("Substitute coverage")
    st.caption(
        "Record who is covering each class day while you are out. Best practice: confirm leave "
        "is **approved** before marking substitutes as **confirmed**."
    )
    approved_or_mine = [
        x
        for x in rows
        if x.get("status") == "approved" or (own_id and str(x.get("teacher_id")) == str(own_id))
    ]
    if not approved_or_mine:
        st.info("No approved (or owned) leave requests yet—submit and get approval first.")
    else:
        labels = {
            str(x["id"]): f"{x.get('start_date', '')} → {x.get('end_date', '')} · {x.get('status', '')}"
            for x in approved_or_mine
        }
        pick = st.selectbox(
            "Attach coverage to leave request",
            options=list(labels.keys()),
            format_func=lambda k: labels[k],
            key="sub_pick_lr",
        )
        if st.button("Load substitute rows", key="sub_refresh"):
            sr = api_request("GET", f"/staff/substitute-plans?leave_request_id={pick}")
            st.session_state["_sub_cache_key"] = pick
            st.session_state["_sub_cache"] = sr.json() if sr.is_success else []
            if not sr.is_success:
                st.error(sr.text)
        if st.session_state.get("_sub_cache_key") == pick and st.session_state.get("_sub_cache") is not None:
            st.dataframe(st.session_state["_sub_cache"], use_container_width=True)

        with st.form("sub_add"):
            cov = st.date_input("Coverage date", value=date.today(), key="sub_cov")
            period = st.text_input("Block / period label", placeholder="e.g., Full day, Periods 3–5")
            sname = st.text_input("Substitute name", placeholder="Guest teacher or agency staff")
            scontact = st.text_input("Substitute contact (optional)")
            hnotes = st.text_area("Handoff notes for coverage", height=70)
            stsel = st.selectbox("Coverage status", ["draft", "confirmed", "in_place", "completed"])
            if st.form_submit_button("Add substitute row"):
                pr = api_request(
                    "POST",
                    "/staff/substitute-plans",
                    json={
                        "leave_request_id": pick,
                        "coverage_date": cov.isoformat(),
                        "period_label": period or None,
                        "substitute_name": sname.strip(),
                        "substitute_contact": scontact.strip() or None,
                        "handoff_notes": hnotes.strip() or None,
                        "status": stsel,
                    },
                )
                if pr.is_success:
                    st.success("Coverage row saved.")
                    st.session_state.pop("_sub_cache", None)
                    st.rerun()
                else:
                    st.error(pr.text)
