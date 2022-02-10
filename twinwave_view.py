def _tree_order_resources(current_node, ordered_resources=[], depth=0):
    ordered_resources.append({"depth": depth, "node": current_node})

    for c in current_node["_children"]:
        _tree_order_resources(c, ordered_resources, depth + 1)

    return ordered_resources


def job_summary(provides, all_app_runs, context):
    context["results"] = results = []
    for summary, action_results in all_app_runs:
        for result in action_results:

            ctx_result = get_ctx_result(result)
            if not ctx_result or not ctx_result["data"]:
                continue

            job = ctx_result["data"]

            resources = job.get("Resources", [])

            for r in resources:
                r["_children"] = [r2 for r2 in resources if r2["ParentID"] == r["ID"]]

            ctx_result["ordered_resources"] = _tree_order_resources([r for r in resources if not r["ParentID"]][0])

            ctx_result["phished_brands"] = [label["Value"] for label in job["Labels"] if label["Type"] == "phished_brand"]
            ctx_result["malware_families"] = [label["Value"] for label in job["Labels"] if label["Type"] == "malware_family"]
            ctx_result["phishkit_families"] = [label["Value"] for label in job["Labels"] if label["Type"] == "phishkit_family"]

            results.append(ctx_result)

    return "job_summary.html"


def get_ctx_result(result):
    ctx_result = {}
    param = result.get_param()
    summary = result.get_summary()
    data = result.get_data()

    ctx_result["param"] = param

    if data:
        ctx_result["data"] = data[0]

    if summary:
        ctx_result["summary"] = summary

    return ctx_result
