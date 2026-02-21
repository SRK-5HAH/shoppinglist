import json
import os
from typing import Dict, List, Any, Tuple
from datetime import date

import streamlit as st
import streamlit.components.v1 as components

# =========================================================
# Shopping List App (Streamlit)
# - Store tiles with category-grouped items
# - Global search across items
# - Right-side shopping list summary + copy-to-clipboard
# - Add stores, categories, items, persisted locally in JSON
# - Copy output formatted for WhatsApp: bold header + underline line + checkbox bullets
# - Sort list by store visit order (editable)
# =========================================================

DATA_FILE = "shopping_data.json"
META_FILE = "shopping_meta.json"

DEFAULT_STORES: Dict[str, Dict[str, List[str]]] = {
    "Costco": {
        "Bakery": ["Bread", "Ritz Crackers"],
        "Dairy": ["Eggs", "Milk", "Cheese", "Butter", "Dahi"],
        "Meat & Frozen": ["Chicken", "Chicken nuggets"],
        "Pantry & Snacks": ["Chips", "Juice", "Nuts", "Cooking oil"],
        "Household": ["Toilet Paper", "Paper Towel"],
    },
    "Walmart": {
        "Pantry": ["Tortillas", "Beans", "Pasta Noodles", "Sauces", "Sugar"],
        "Dairy": ["Sour cream"],
        "Produce": ["Veggies", "Fruits", "Tomato", "Potato", "Bell peppers", "Onion"],
    },
    "Indian Store": {
        "Staples": ["Rice", "Daal", "Pulses"],
        "Spices": ["Masalas"],
        "Convenience": ["Maggie noodles", "Mango pulp"],
    },
    "Marianos": {
        "Uncategorized": []
    },
}

DEFAULT_STORE_ORDER = ["Costco", "Walmart", "Indian Store", "Marianos"]

CHECKBOX_BULLET = "☐"   # Looks good in WhatsApp
UNDERLINE_CHAR = "—"    # Use a simple underline line; WhatsApp doesn't support true underline


# -----------------------------
# Basic helpers
# -----------------------------
def normalize_name(name: str) -> str:
    return " ".join(str(name).strip().split())


def _sorted_unique(items: List[str]) -> List[str]:
    clean = [normalize_name(x) for x in items if normalize_name(x)]
    return sorted(list(set(clean)), key=lambda s: s.lower())


# -----------------------------
# Data loading/saving
# -----------------------------
def convert_legacy_shape(data: Dict[str, Any]) -> Dict[str, Dict[str, List[str]]]:
    """
    Convert:
      {store:[items]} to {store:{'Uncategorized':[items]}}
    Keep:
      {store:{category:[items]}}
    Ignore any accidental meta keys if present.
    """
    converted: Dict[str, Dict[str, List[str]]] = {}

    for store, payload in data.items():
        store_name = normalize_name(store)
        if not store_name:
            continue

        # If someone created a store literally named "_meta", treat it as a store anyway.
        # We keep meta in a separate file, so no special-casing is needed.

        if isinstance(payload, list):
            converted[store_name] = {"Uncategorized": _sorted_unique([str(x) for x in payload])}
        elif isinstance(payload, dict):
            cat_map: Dict[str, List[str]] = {}
            for cat, items in payload.items():
                cat_name = normalize_name(cat) or "Uncategorized"
                if isinstance(items, list):
                    cat_map[cat_name] = _sorted_unique([str(x) for x in items])
            if not cat_map:
                cat_map = {"Uncategorized": []}
            converted[store_name] = cat_map
        else:
            converted[store_name] = {"Uncategorized": []}

    return converted


def load_stores() -> Dict[str, Dict[str, List[str]]]:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                cleaned = convert_legacy_shape(raw)
                return cleaned if cleaned else DEFAULT_STORES.copy()
        except Exception:
            return DEFAULT_STORES.copy()
    return DEFAULT_STORES.copy()


def save_stores(stores: Dict[str, Dict[str, List[str]]]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(stores, f, indent=2, ensure_ascii=False)


def load_store_order(stores: Dict[str, Dict[str, List[str]]]) -> List[str]:
    """
    Load user-defined store visit order.
    If missing, use DEFAULT_STORE_ORDER plus any additional stores appended.
    """
    order: List[str] = []
    if os.path.exists(META_FILE):
        try:
            with open(META_FILE, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if isinstance(meta, dict) and isinstance(meta.get("store_order"), list):
                order = [normalize_name(x) for x in meta["store_order"] if normalize_name(x)]
        except Exception:
            order = []

    # Seed order if empty
    if not order:
        order = DEFAULT_STORE_ORDER.copy()

    # Remove stores that no longer exist
    order = [s for s in order if s in stores]

    # Append any stores not already in order
    for s in sorted(stores.keys(), key=lambda x: x.lower()):
        if s not in order:
            order.append(s)

    return order


def save_store_order(order: List[str]) -> None:
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump({"store_order": order}, f, indent=2, ensure_ascii=False)


def add_store(stores: Dict[str, Dict[str, List[str]]], store_name: str) -> Dict[str, Dict[str, List[str]]]:
    store_name = normalize_name(store_name)
    if store_name and store_name not in stores:
        stores[store_name] = {"Uncategorized": []}
    return stores


def add_category(stores: Dict[str, Dict[str, List[str]]], store_name: str, category_name: str) -> Dict[str, Dict[str, List[str]]]:
    store_name = normalize_name(store_name)
    category_name = normalize_name(category_name) or "Uncategorized"
    if store_name in stores and category_name not in stores[store_name]:
        stores[store_name][category_name] = []
    return stores


def add_items(stores: Dict[str, Dict[str, List[str]]], store_name: str, category_name: str, items_text: str) -> Dict[str, Dict[str, List[str]]]:
    store_name = normalize_name(store_name)
    category_name = normalize_name(category_name) or "Uncategorized"
    if store_name not in stores:
        return stores
    if category_name not in stores[store_name]:
        stores[store_name][category_name] = []

    raw = items_text.replace("\n", ",")
    new_items = [normalize_name(x) for x in raw.split(",")]
    new_items = [x for x in new_items if x]

    merged = set(stores[store_name][category_name])
    for item in new_items:
        merged.add(item)

    stores[store_name][category_name] = sorted(merged, key=lambda s: s.lower())
    return stores


def remove_item(stores: Dict[str, Dict[str, List[str]]], store_name: str, category_name: str, item: str) -> Dict[str, Dict[str, List[str]]]:
    if store_name in stores and category_name in stores[store_name]:
        stores[store_name][category_name] = [x for x in stores[store_name][category_name] if x != item]
    return stores


def remove_category(stores: Dict[str, Dict[str, List[str]]], store_name: str, category_name: str) -> Dict[str, Dict[str, List[str]]]:
    if store_name in stores and category_name in stores[store_name]:
        if len(stores[store_name]) > 1:
            del stores[store_name][category_name]
        else:
            stores[store_name] = {"Uncategorized": []}
    return stores


def remove_store(stores: Dict[str, Dict[str, List[str]]], store_name: str) -> Dict[str, Dict[str, List[str]]]:
    if store_name in stores:
        del stores[store_name]
    return stores


# -----------------------------
# UI helpers
# -----------------------------
def store_color(store: str) -> str:
    s = store.lower()
    if "costco" in s:
        return "#D62828"
    if "walmart" in s:
        return "#1D9BF0"
    if "indian" in s:
        return "#2B2B2B"
    if "maria" in s:
        return "#6B4F2A"
    return "#2B2B2B"


def chunk_list(items: List[str], n: int) -> List[List[str]]:
    return [items[i:i + n] for i in range(0, len(items), n)]


def ordered_stores(store_order: List[str], stores: Dict[str, Any]) -> List[str]:
    """
    Return stores in visit order first, then anything else alphabetically.
    """
    seen = set()
    out: List[str] = []

    for s in store_order:
        if s in stores and s not in seen:
            out.append(s)
            seen.add(s)

    for s in sorted(stores.keys(), key=lambda x: x.lower()):
        if s not in seen:
            out.append(s)
            seen.add(s)

    return out


def format_shopping_list_for_whatsapp(
    selected: Dict[str, Dict[str, List[str]]],
    store_order: List[str],
) -> str:
    """
    Clean WhatsApp output:
    - First line: current date
    - Store header is bold (*Store*)
    - Underline is simulated with a line of characters
    - Items are a single checklist (no category headings)
    """
    today = date.today().strftime("%b %d, %Y")  # Example: Feb 21, 2026
    lines: List[str] = [f"Shopping List - {today}", ""]

    stores_in_order = ordered_stores(store_order, selected)

    for store in stores_in_order:
        cat_map = selected.get(store, {})

        # Flatten items across categories
        all_items: List[str] = []
        for cat in cat_map:
            all_items.extend(cat_map[cat])

        # Remove empties and duplicates, sort
        all_items = [normalize_name(x) for x in all_items if normalize_name(x)]
        all_items = sorted(list(set(all_items)), key=lambda s: s.lower())

        if not all_items:
            continue

        header = f"*{store}*"
        underline = UNDERLINE_CHAR * max(6, min(22, len(store) + 2))

        lines.append(header)
        lines.append(underline)

        for it in all_items:
            lines.append(f"{CHECKBOX_BULLET} {it}")

        lines.append("")  # blank line between stores

    return "\n".join(lines).strip()


def copy_button(text_to_copy: str, label: str = "Copy list") -> None:
    safe_text = (
        text_to_copy.replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("${", "\\${")
    )
    components.html(
        f"""
        <div style="display:flex; gap:10px; align-items:center; margin: 6px 0 14px 0;">
          <button id="copyBtn"
                  style="
                    background:#111827; color:white; border:none; border-radius:10px;
                    padding:10px 14px; cursor:pointer; font-size:14px;">
            {label}
          </button>
          <span id="copyStatus" style="font-size:13px; color:#374151;"></span>
        </div>
        <script>
          const btn = document.getElementById("copyBtn");
          const status = document.getElementById("copyStatus");
          const text = `{safe_text}`;

          btn.addEventListener("click", async () => {{
            try {{
              await navigator.clipboard.writeText(text);
              status.textContent = "Copied!";
              setTimeout(() => status.textContent = "", 1500);
            }} catch(e) {{
              status.textContent = "Copy failed. Select and copy manually.";
            }}
          }});
        </script>
        """,
        height=60,
    )


def parse_store_order_text(text: str, stores: Dict[str, Any]) -> List[str]:
    """
    Parse one store per line, keep only valid stores, append missing ones.
    """
    lines = [normalize_name(x) for x in text.splitlines()]
    lines = [x for x in lines if x and x in stores]

    # Keep unique, in entered order
    out: List[str] = []
    seen = set()
    for s in lines:
        if s not in seen:
            out.append(s)
            seen.add(s)

    # Append any stores not listed
    for s in sorted(stores.keys(), key=lambda x: x.lower()):
        if s not in seen:
            out.append(s)
            seen.add(s)

    return out


# -----------------------------
# App
# -----------------------------
st.set_page_config(page_title="Shopping List App", page_icon="🛒", layout="wide")

if "stores" not in st.session_state:
    st.session_state.stores = load_stores()

stores: Dict[str, Dict[str, List[str]]] = st.session_state.stores

if "store_order" not in st.session_state:
    st.session_state.store_order = load_store_order(stores)

# Selection state:
# selected[store][category] = set(items)
if "selected" not in st.session_state:
    st.session_state.selected = {s: {c: set() for c in stores[s].keys()} for s in stores}

# Keep selection aligned with stores/categories
for store in list(st.session_state.selected.keys()):
    if store not in stores:
        del st.session_state.selected[store]
for store in stores:
    st.session_state.selected.setdefault(store, {})
    for cat in stores[store]:
        st.session_state.selected[store].setdefault(cat, set())
    for cat in list(st.session_state.selected[store].keys()):
        if cat not in stores[store]:
            del st.session_state.selected[store][cat]

# Keep store order aligned
st.session_state.store_order = load_store_order(stores)

# Styling
st.markdown(
    """
    <style>
      .tile {
        border: 1px solid rgba(0,0,0,0.08);
        border-radius: 16px;
        padding: 14px 14px 10px 14px;
        box-shadow: 0 8px 22px rgba(0,0,0,0.06);
        background: white;
      }
      .tile-title {
        font-size: 28px;
        font-weight: 800;
        line-height: 1.1;
        margin-bottom: 6px;
      }
      .subtle {
        color: rgba(0,0,0,0.55);
        font-size: 13px;
        margin-top: -2px;
        margin-bottom: 8px;
      }
      .divider {
        height: 1px;
        background: rgba(0,0,0,0.08);
        margin: 10px 0 12px 0;
      }
      .cat {
        font-weight: 700;
        margin: 8px 0 6px 0;
      }
      .hint {
        font-size: 12px;
        color: rgba(0,0,0,0.55);
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# Header
left_head, right_head = st.columns([3, 2], vertical_alignment="center")
with left_head:
    st.title("Shopping List App")
    st.caption("Select items by store and category, then copy the list to paste into WhatsApp or Notes.")

with right_head:
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Clear selections", use_container_width=True):
            for s in st.session_state.selected:
                for c in st.session_state.selected[s]:
                    st.session_state.selected[s][c] = set()
            st.rerun()
    with c2:
        if st.button("Save stores/items", use_container_width=True):
            save_stores(stores)
            save_store_order(st.session_state.store_order)
            st.success("Saved!")
    with c3:
        if st.button("Reset to defaults", use_container_width=True):
            st.session_state.stores = DEFAULT_STORES.copy()
            stores = st.session_state.stores
            st.session_state.selected = {s: {c: set() for c in stores[s].keys()} for s in stores}
            st.session_state.store_order = load_store_order(stores)
            save_stores(stores)
            save_store_order(st.session_state.store_order)
            st.rerun()

st.write("")

# Search (global)
search = st.text_input("Search items (across all stores)", placeholder="Type: milk, rice, toilet paper...")
search_norm = normalize_name(search).lower()

main_col, list_col = st.columns([3.2, 1.6], gap="large")

# Right panel: list
with list_col:
    st.subheader("Your Shopping List")

    # Build output structure from selection
    selected_for_output: Dict[str, Dict[str, List[str]]] = {}
    for store in stores:
        selected_for_output[store] = {}
        for cat in stores[store]:
            items = sorted(list(st.session_state.selected[store].get(cat, set())), key=lambda s: s.lower())
            selected_for_output[store][cat] = items

    list_text = format_shopping_list_for_whatsapp(selected_for_output, st.session_state.store_order)

    if list_text.strip():
        copy_button(list_text, label="Copy list")
        st.text_area("Copy-ready text", value=list_text, height=360)
        st.caption("Paste into WhatsApp. Store names are bold, items have ☐ checkboxes.")
    else:
        st.info("Select items from the store tiles to build your list.")

    st.markdown("---")

    st.subheader("Sort by store visit order")
    st.markdown("<div class='hint'>One store per line. The list will follow this order.</div>", unsafe_allow_html=True)

    order_text_default = "\n".join(st.session_state.store_order)
    order_text = st.text_area(
        "Store order",
        value=order_text_default,
        height=140,
        label_visibility="collapsed",
    )

    if st.button("Update store order"):
        new_order = parse_store_order_text(order_text, stores)
        st.session_state.store_order = new_order
        save_store_order(new_order)
        st.success("Store visit order updated.")
        st.rerun()

    st.markdown("---")
    st.subheader("Add / Edit")

    with st.expander("Add a new store", expanded=False):
        new_store = st.text_input("Store name", placeholder="Example: Target")
        if st.button("Add store"):
            new_store = normalize_name(new_store)
            if not new_store:
                st.warning("Enter a store name.")
            elif new_store in stores:
                st.warning("That store already exists.")
            else:
                stores = add_store(stores, new_store)
                st.session_state.stores = stores
                st.session_state.selected.setdefault(new_store, {"Uncategorized": set()})
                st.session_state.store_order = load_store_order(stores)
                save_stores(stores)
                save_store_order(st.session_state.store_order)
                st.success(f"Added: {new_store}")
                st.rerun()

    with st.expander("Add a category to a store", expanded=False):
        store_for_cat = st.selectbox("Choose store", options=sorted(stores.keys(), key=lambda s: s.lower()), key="add_cat_store")
        new_cat = st.text_input("Category name", placeholder="Example: Household, Produce, Dairy")
        if st.button("Add category"):
            new_cat = normalize_name(new_cat) or "Uncategorized"
            stores = add_category(stores, store_for_cat, new_cat)
            st.session_state.stores = stores
            st.session_state.selected[store_for_cat].setdefault(new_cat, set())
            save_stores(stores)
            st.success(f"Added category: {new_cat}")
            st.rerun()

    with st.expander("Add products to a store category", expanded=False):
        store_for_items = st.selectbox("Choose store", options=sorted(stores.keys(), key=lambda s: s.lower()), key="add_items_store")
        existing_cats = sorted(stores[store_for_items].keys(), key=lambda s: s.lower())
        cat_pick = st.selectbox("Choose category", options=existing_cats + ["+ Create new category"], key="add_items_cat")

        if cat_pick == "+ Create new category":
            cat_name = st.text_input("New category name", placeholder="Example: Pantry")
        else:
            cat_name = cat_pick

        items_text = st.text_area(
            "Products (comma or new line separated)",
            placeholder="Example:\nYogurt\nCereal\nOr: Yogurt, Cereal",
            height=120,
        )

        if st.button("Add products"):
            cat_name = normalize_name(cat_name) or "Uncategorized"
            if not items_text.strip():
                st.warning("Enter at least one product.")
            else:
                stores = add_items(stores, store_for_items, cat_name, items_text)
                st.session_state.stores = stores
                st.session_state.selected[store_for_items].setdefault(cat_name, set())
                save_stores(stores)
                st.success("Products added.")
                st.rerun()

    with st.expander("Remove a product, category, or store", expanded=False):
        store_rm = st.selectbox("Store", options=["(choose)"] + sorted(stores.keys(), key=lambda s: s.lower()), key="rm_store")
        if store_rm != "(choose)":
            cats_rm = sorted(stores[store_rm].keys(), key=lambda s: s.lower())
            cat_rm = st.selectbox("Category", options=["(choose)"] + cats_rm, key="rm_cat")

            if cat_rm != "(choose)":
                items_rm = stores[store_rm][cat_rm]
                if items_rm:
                    item_rm = st.selectbox("Product", options=["(choose)"] + items_rm, key="rm_item")
                    if item_rm != "(choose)":
                        if st.button("Remove product"):
                            stores = remove_item(stores, store_rm, cat_rm, item_rm)
                            st.session_state.stores = stores
                            st.session_state.selected[store_rm][cat_rm].discard(item_rm)
                            save_stores(stores)
                            st.success(f"Removed: {item_rm}")
                            st.rerun()
                else:
                    st.caption("No products in this category.")

                st.write("")
                if st.button("Remove category"):
                    stores = remove_category(stores, store_rm, cat_rm)
                    st.session_state.stores = stores
                    if cat_rm in st.session_state.selected[store_rm]:
                        del st.session_state.selected[store_rm][cat_rm]
                    save_stores(stores)
                    st.success(f"Removed category: {cat_rm}")
                    st.rerun()

            st.write("")
            if st.button("Remove store"):
                stores = remove_store(stores, store_rm)
                st.session_state.stores = stores
                if store_rm in st.session_state.selected:
                    del st.session_state.selected[store_rm]
                st.session_state.store_order = load_store_order(stores)
                save_stores(stores)
                save_store_order(st.session_state.store_order)
                st.success(f"Removed store: {store_rm}")
                st.rerun()

# Left panel: store tiles
with main_col:
    # Keep tile order alphabetical (nice scanning), list order is visit-order
    store_names = sorted(stores.keys(), key=lambda s: s.lower())
    rows = chunk_list(store_names, 2)

    for row in rows:
        cols = st.columns(2, gap="large")
        for i, store in enumerate(row):
            with cols[i]:
                color = store_color(store)
                st.markdown("<div class='tile'>", unsafe_allow_html=True)
                st.markdown(
                    f"<div class='tile-title' style='color:{color};'>{store}</div>"
                    f"<div class='subtle'>Pick items by category</div>"
                    f"<div class='divider'></div>",
                    unsafe_allow_html=True,
                )

                cat_map = stores.get(store, {})
                any_visible = False

                for cat in sorted(cat_map.keys(), key=lambda s: s.lower()):
                    items = cat_map[cat]

                    # Filter by search
                    if search_norm:
                        visible_items = [it for it in items if search_norm in it.lower()]
                    else:
                        visible_items = items

                    if not visible_items:
                        continue

                    any_visible = True
                    st.markdown(f"<div class='cat'>{cat}</div>", unsafe_allow_html=True)

                    for item in visible_items:
                        key = f"chk::{store}::{cat}::{item}"
                        default_checked = item in st.session_state.selected[store][cat]
                        checked = st.checkbox(item, value=default_checked, key=key)

                        if checked:
                            st.session_state.selected[store][cat].add(item)
                        else:
                            st.session_state.selected[store][cat].discard(item)

                if not any_visible:
                    if search_norm:
                        st.caption("No matches in this store.")
                    else:
                        st.caption("No products yet. Add some from the right panel.")

                st.markdown("</div>", unsafe_allow_html=True)

st.caption("Tip: Select items, then Copy list and paste into WhatsApp. Use the store order box to match your shopping route.")