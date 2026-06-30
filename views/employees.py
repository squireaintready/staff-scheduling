"""Employee management view: add, edit, deactivate, delete."""


import streamlit as st

import database as db


def render():
    """Employee management page."""
    st.header("Employee Management")

    # Add new employee section
    st.subheader("Add New Employee")
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        new_name = st.text_input("Name", key="new_emp_name", placeholder="Enter employee name")
    with col2:
        new_rate = st.number_input("Hourly Rate ($)", min_value=1.0,
                                   max_value=500.0, value=10.0, step=0.50,
                                   key="new_emp_rate")
    with col3:
        st.write("")  # Spacer
        st.write("")
        if st.button("Add Employee", type="primary"):
            if new_name.strip():
                db.add_employee(new_name.strip(), new_rate)
                st.success(f"Added {new_name}")
                st.rerun()
            else:
                st.error("Please enter a name")

    st.divider()

    # Get active and inactive employees separately
    all_employees = db.get_employees(active_only=False)
    active_employees = [e for e in all_employees if e['is_active']]
    inactive_employees = [e for e in all_employees if not e['is_active']]

    if not all_employees:
        st.info("No employees yet. Add your first employee above.")
        return

    # Active employees section
    st.subheader("Current Employees")
    if active_employees:
        st.caption("Click on an employee to edit their details")
        for emp in active_employees:
            label = f"**{emp['name']}** - ${emp['hourly_rate']:.2f}/hr"

            with st.expander(label):
                edit_cols = st.columns([2, 2, 1])

                with edit_cols[0]:
                    new_name = st.text_input(
                        "Name",
                        value=emp['name'],
                        key=f"emp_name_{emp['id']}"
                    )

                with edit_cols[1]:
                    new_rate = st.number_input(
                        "Hourly Rate ($)",
                        min_value=1.0,
                        max_value=500.0,
                        value=float(emp['hourly_rate']),
                        step=0.50,
                        key=f"emp_rate_{emp['id']}"
                    )

                with edit_cols[2]:
                    st.write("")
                    st.write("")
                    if st.button("Update", key=f"save_emp_{emp['id']}", type="primary"):
                        db.update_employee(emp['id'], name=new_name, hourly_rate=new_rate)
                        st.success("Updated!")
                        st.rerun()

                if st.button("Deactivate Employee", key=f"deact_emp_{emp['id']}"):
                    db.update_employee(emp['id'], is_active=False)
                    st.rerun()
    else:
        st.info("No active employees. Reactivate employees below or add new ones above.")

    # Inactive employees section
    if inactive_employees:
        st.divider()
        st.subheader("Inactive Employees")
        for emp in inactive_employees:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{emp['name']}** - ${emp['hourly_rate']:.2f}/hr")
            with col2:
                if st.button("Reactivate", key=f"reactivate_{emp['id']}"):
                    db.update_employee(emp['id'], is_active=True)
                    st.rerun()
            with col3:
                if st.button("Delete", key=f"delete_emp_{emp['id']}", type="secondary"):
                    st.session_state[f'confirm_delete_{emp["id"]}'] = True
                    st.rerun()

            # Confirmation dialog
            if st.session_state.get(f'confirm_delete_{emp["id"]}'):
                st.warning(f"Permanently delete **{emp['name']}**? This will also delete all their shift history.")
                c1, c2, c3 = st.columns([1, 1, 2])
                with c1:
                    if st.button("Yes, Delete", key=f"confirm_del_{emp['id']}", type="primary"):
                        db.hard_delete_employee(emp['id'])
                        del st.session_state[f'confirm_delete_{emp["id"]}']
                        st.rerun()
                with c2:
                    if st.button("Cancel", key=f"cancel_del_{emp['id']}"):
                        del st.session_state[f'confirm_delete_{emp["id"]}']
                        st.rerun()
