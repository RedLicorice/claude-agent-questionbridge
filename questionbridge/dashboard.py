from nicegui import ui
from . import store


def _status_chip_props(status: str) -> str:
    colors = {
        "pending": "color=orange",
        "answered": "color=positive",
        "cancelled": "color=grey",
    }
    return colors.get(status, "color=grey")


@ui.page("/")
async def dashboard():
    ui.add_head_html('<meta name="viewport" content="width=device-width, initial-scale=1.0">')

    with ui.column().classes("w-full max-w-2xl mx-auto p-6 gap-4"):
        # Header
        with ui.row().classes("w-full items-center justify-between"):
            with ui.row().classes("items-baseline gap-3"):
                ui.label("QuestionBridge").classes("text-3xl font-bold tracking-tight")
                ui.label("owner dashboard").classes("text-gray-400 text-sm")

            away_toggle = ui.toggle(
                {False: "🟢 Here", True: "🌙 Away"},
                value=store.away,
            ).props("dense")

            async def on_toggle(e):
                store.away = e.value

            away_toggle.on("update:model-value", on_toggle)

        ui.separator()

        pending_area = ui.column().classes("w-full gap-3")
        history_area = ui.column().classes("w-full gap-2 mt-2")

        async def refresh():
            pending_area.clear()
            history_area.clear()

            pending = [q for q in store.questions.values() if q.status == "pending"]
            done = sorted(
                [q for q in store.questions.values() if q.status != "pending"],
                key=lambda q: q.answered_at or q.created_at,
                reverse=True,
            )

            # ── Pending section ────────────────────────────────────────────
            with pending_area:
                with ui.row().classes("items-center gap-2"):
                    ui.label("Pending").classes("text-lg font-semibold text-orange-500")
                    ui.badge(str(len(pending)), color="orange").props("rounded")

                if not pending:
                    with ui.card().classes("w-full"):
                        ui.label("No pending questions — all clear!").classes(
                            "text-gray-400 italic text-sm text-center w-full py-2"
                        )

                for q in pending:
                    with ui.card().classes("w-full shadow"):
                        with ui.row().classes("w-full justify-between items-center mb-2"):
                            ui.label(q.id).classes(
                                "font-mono text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded"
                            )
                            ui.label(q.created_at.strftime("%H:%M:%S UTC")).classes(
                                "text-xs text-gray-400"
                            )

                        ui.label(q.question).classes(
                            "text-base font-medium whitespace-pre-wrap break-words"
                        )

                        if q.context:
                            with ui.expansion("📎 Context").classes("w-full text-sm mt-1"):
                                ui.label(q.context).classes(
                                    "text-gray-600 whitespace-pre-wrap text-sm"
                                )

                        inp = ui.input(placeholder="Free-text answer…").classes("w-full mt-3")

                        def make_text_submit(qid, field):
                            async def _h():
                                val = field.value.strip()
                                if val:
                                    store.answer_question(qid, val)
                                    await refresh()
                            return _h

                        def make_quick(qid, val):
                            async def _h():
                                store.answer_question(qid, val)
                                await refresh()
                            return _h

                        def make_cancel(qid):
                            async def _h():
                                store.cancel_question(qid)
                                await refresh()
                            return _h

                        with ui.row().classes("gap-2 mt-2 flex-wrap"):
                            ui.button("✅ Yes", on_click=make_quick(q.id, "yes")).props(
                                "unelevated color=positive"
                            )
                            ui.button("❌ No", on_click=make_quick(q.id, "no")).props(
                                "unelevated color=negative"
                            )
                            ui.button("Submit", on_click=make_text_submit(q.id, inp)).props(
                                "unelevated color=primary"
                            )
                            ui.button("Cancel", on_click=make_cancel(q.id)).props(
                                "flat color=grey"
                            )

            # ── History section ────────────────────────────────────────────
            with history_area:
                if done:
                    ui.label("History").classes("text-lg font-semibold text-gray-400 mt-2")
                    for q in done[:30]:
                        with ui.card().classes("w-full opacity-80"):
                            with ui.row().classes("w-full justify-between items-center"):
                                ui.label(q.id).classes("font-mono text-xs text-gray-400")
                                ui.chip(
                                    q.status.upper(),
                                    icon="check_circle" if q.status == "answered" else "cancel",
                                ).props(_status_chip_props(q.status) + " dense outline")

                            preview = q.question[:120]
                            if len(q.question) > 120:
                                preview += "…"
                            ui.label(preview).classes("text-sm text-gray-700 whitespace-pre-wrap")

                            if q.answer:
                                ui.label(f"→ {q.answer}").classes(
                                    "text-sm font-semibold text-blue-600 mt-1"
                                )

        await refresh()
        ui.timer(2.0, refresh)
