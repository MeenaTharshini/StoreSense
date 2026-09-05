"""
StoreSense Recommendation Engine

Deterministic recommendation logic.
Gemini should explain these recommendations, not invent them.
"""


def replenishment(
    daily_demand: float,
    current_stock: float,
    target_days: int = 7
) -> dict:
    """
    Calculate recommended replenishment quantity.

    Formula:
        recommended_stock = daily_demand × target_days

        replenishment =
            max(0, recommended_stock - current_stock)
    """

    daily_demand = max(float(daily_demand), 0.0)
    current_stock = max(float(current_stock), 0.0)

    target_stock = daily_demand * target_days

    quantity = max(
        0,
        round(target_stock - current_stock)
    )

    return {
        "daily_demand": round(daily_demand, 2),
        "current_stock": round(current_stock, 2),
        "target_days": target_days,
        "target_stock": round(target_stock, 2),
        "recommended_quantity": quantity,
        "formula": (
            f"{daily_demand:.2f} × {target_days} "
            f"− {current_stock:.0f} = {quantity}"
        )
    }


def action_for_alert(alert: dict) -> dict:
    """
    Convert an analytics alert into a deterministic action.

    The function is intentionally rule-based so that
    recommendations remain grounded in actual data.
    """

    alert_type = str(
        alert.get("type", "")
    ).lower()

    priority = str(
        alert.get("priority", "medium")
    ).lower()

    product_name = alert.get(
        "product_name",
        "this product"
    )

    store_name = alert.get(
        "store_name",
        "this store"
    )

    # -----------------------------------------------------
    # Stockout risk
    # -----------------------------------------------------

    if (
        "stockout" in alert_type
        or "stock_out" in alert_type
        or "low_stock" in alert_type
    ):

        daily_demand = float(
            alert.get("daily_demand", 0)
        )

        current_stock = float(
            alert.get("current_stock", alert.get("stock", 0))
        )

        recommendation = replenishment(
            daily_demand=daily_demand,
            current_stock=current_stock,
            target_days=7
        )

        days_left = (
            current_stock / daily_demand
            if daily_demand > 0
            else None
        )

        if days_left is not None:
            days_text = f"{days_left:.2f} days"
        else:
            days_text = "unknown"

        return {
            "action": "Replenish stock",
            "priority": (
                "high"
                if priority == "high"
                else priority
            ),
            "reason": (
                f"{product_name} at {store_name} "
                f"has approximately {days_text} of stock coverage."
            ),
            "recommendation": recommendation,
            "assumptions": [
                "Recent average daily demand represents near-term demand.",
                "A 7-day stock coverage target is appropriate.",
                "No major supply disruption is assumed."
            ]
        }

    # -----------------------------------------------------
    # Slow moving
    # -----------------------------------------------------

    if (
        "slow" in alert_type
        or "non_moving" in alert_type
        or "not_moving" in alert_type
    ):

        stock = float(
            alert.get(
                "current_stock",
                alert.get("stock", 0)
            )
        )

        units_sold = float(
            alert.get(
                "recent_units",
                alert.get("units_sold", 0)
            )
        )

        return {
            "action": "Investigate slow-moving stock",
            "priority": priority,
            "reason": (
                f"{product_name} at {store_name} "
                f"has {stock:.0f} units in stock while "
                f"only {units_sold:.0f} units were sold "
                f"in the recent period."
            ),
            "recommendation": {
                "suggested_action": (
                    "Pause replenishment and consider "
                    "promotion, redistribution, or markdown."
                ),
                "current_stock": round(stock, 2),
                "recent_units_sold": round(units_sold, 2)
            },
            "assumptions": [
                "The recent sales period is representative.",
                "No known promotion or seasonal event is distorting demand."
            ]
        }

    # -----------------------------------------------------
    # Sales spike
    # -----------------------------------------------------

    if (
        "spike" in alert_type
        or "increase" in alert_type
    ):

        change_pct = float(
            alert.get(
                "change_pct",
                alert.get("change_percent", 0)
            )
        )

        return {
            "action": "Investigate sales increase",
            "priority": priority,
            "reason": (
                f"{product_name} at {store_name} "
                f"shows a {change_pct:.1f}% increase in sales."
            ),
            "recommendation": {
                "suggested_action": (
                    "Check stock availability, promotions, "
                    "and whether the demand increase is sustainable."
                ),
                "change_percent": round(change_pct, 2)
            },
            "assumptions": [
                "The comparison period is valid.",
                "The increase is not caused solely by a data-entry anomaly."
            ]
        }

    # -----------------------------------------------------
    # Sales drop
    # -----------------------------------------------------

    if (
        "drop" in alert_type
        or "decrease" in alert_type
        or "decline" in alert_type
    ):

        change_pct = float(
            alert.get(
                "change_pct",
                alert.get("change_percent", 0)
            )
        )

        return {
            "action": "Investigate sales decline",
            "priority": priority,
            "reason": (
                f"{product_name} at {store_name} "
                f"shows a {abs(change_pct):.1f}% decline in sales."
            ),
            "recommendation": {
                "suggested_action": (
                    "Check pricing, promotions, product availability, "
                    "and recent customer demand."
                ),
                "change_percent": round(change_pct, 2)
            },
            "assumptions": [
                "The comparison period is valid.",
                "There is no known temporary stock or store closure issue."
            ]
        }

    # -----------------------------------------------------
    # Overstock
    # -----------------------------------------------------

    if (
        "overstock" in alert_type
        or "excess" in alert_type
    ):

        stock = float(
            alert.get(
                "current_stock",
                alert.get("stock", 0)
            )
        )

        return {
            "action": "Review excess inventory",
            "priority": priority,
            "reason": (
                f"{product_name} at {store_name} "
                f"has {stock:.0f} units currently in stock."
            ),
            "recommendation": {
                "suggested_action": (
                    "Pause replenishment and consider "
                    "redistribution or promotion."
                ),
                "current_stock": round(stock, 2)
            },
            "assumptions": [
                "Current inventory is accurate.",
                "No upcoming demand event is expected."
            ]
        }

    # -----------------------------------------------------
    # Unknown alert
    # -----------------------------------------------------

    return {
        "action": "Investigate",
        "priority": priority,
        "reason": (
            f"StoreSense detected an attention item for "
            f"{product_name} at {store_name}, "
            f"but the available data does not support "
            f"a more specific action."
        ),
        "recommendation": {
            "suggested_action": (
                "Review the evidence before taking action."
            )
        },
        "assumptions": [
            "No unsupported conclusion is made when evidence is insufficient."
        ]
    }