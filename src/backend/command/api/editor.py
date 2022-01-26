import os

from command.controller.workspace_manager import WorkspaceManager
from flask import Blueprint, jsonify, request, url_for
from utils import exceptions

bp = Blueprint('editor', __name__, url_prefix='/AAZ/Editor')


@bp.route("/Workspaces", methods=("GET", "POST"))
def editor_workspaces():
    if request.method == "POST":
        # create a new workspace
        # the name of workspace is required
        data = request.get_json()
        if not data or not isinstance(data, dict) or 'name' not in data or 'plane' not in data:
            raise exceptions.InvalidAPIUsage("Invalid request body")
        name = data['name']
        plane = data['plane']
        manager = WorkspaceManager.new(name, plane)
        manager.save()
        result = manager.ws.to_primitive()
        result.update({
            'url': url_for('editor.editor_workspace', name=manager.name),
            'folder': manager.folder,
            'updated': os.path.getmtime(manager.path)
        })
    elif request.method == "GET":
        result = []
        for ws in WorkspaceManager.list_workspaces():
            result.append({
                **ws,
                'url': url_for('editor.editor_workspace', name=ws['name']),
            })
    else:
        raise NotImplementedError(request.method)

    return jsonify(result)


@bp.route("/Workspaces/<name>", methods=("GET", "DELETE"))
def editor_workspace(name):
    manager = WorkspaceManager(name)
    if request.method == "GET":
        manager.load()
    elif request.method == "DELETE":
        if manager.delete():
            return '', 200
        else:
            return '', 204  # resource not found
    else:
        raise NotImplementedError()

    result = manager.ws.to_primitive()
    result.update({
        'url': url_for('editor.editor_workspace', name=manager.name),
        'folder': manager.folder,
        'updated': os.path.getmtime(manager.path)
    })
    return jsonify(result)


@bp.route("/Workspaces/<name>/Generate", methods=("POST",))
def editor_workspace_generate(name):
    # generate code and command configurations in cli repos and aaz repo
    raise NotImplementedError()


# command tree operations
@bp.route("/Workspaces/<name>/CommandTree/Nodes/<names_path:node_names>", methods=("GET", "PATCH", "DELETE"))
def editor_workspace_command_tree_node(name, node_names):
    if node_names[0] != WorkspaceManager.COMMAND_TREE_ROOT_NAME:
        raise exceptions.ResourceNotFind("Command group not exist")
    node_names = node_names[1:]

    manager = WorkspaceManager(name)
    manager.load()
    node = manager.find_command_tree_node(*node_names)
    if not node:
        raise exceptions.ResourceNotFind("Command group not exist")

    if request.method == "GET":
        result = node.to_primitive()
    elif request.method == "PATCH":
        data = request.get_json()
        if 'help' in data:
            node = manager.update_command_tree_node_help(*node_names, help=data['help'])
        if 'stage' in data and node.stage != data['stage']:
            node = manager.update_command_tree_node_stage(*node_names, stage=data['stage'])
        manager.save()
        result = node.to_primitive()
    elif request.method == "DELETE":
        if len(node_names) < 1:
            raise exceptions.InvalidAPIUsage("Not support to delete command tree root")
        if manager.delete_command_tree_node(*node_names):
            return '', 200
        else:
            return '', 204  # resource not found
    else:
        raise NotImplementedError()
    return jsonify(result)


@bp.route("/Workspaces/<name>/CommandTree/Nodes/<names_path:node_names>/Rename", methods=("POST",))
def editor_workspace_command_tree_node_rename(name, node_names):
    if node_names[0] != WorkspaceManager.COMMAND_TREE_ROOT_NAME:
        raise exceptions.ResourceNotFind("Command group not exist")
    node_names = node_names[1:]
    if not node_names:
        raise exceptions.InvalidAPIUsage("Cannot Rename root node")

    manager = WorkspaceManager(name)
    manager.load()
    if not manager.find_command_tree_node(*node_names):
        raise exceptions.ResourceNotFind("Command group not exist")

    data = request.get_json()
    new_name = data.get("name", None)
    if not new_name or not isinstance(new_name, str):
        raise exceptions.InvalidAPIUsage("Invalid request")

    new_node_names = new_name.split(' ')
    node = manager.rename_command_tree_node(*node_names, new_node_names=new_node_names)
    result = node.to_primitive()
    return jsonify(result)


@bp.route("/Workspaces/<name>/CommandTree/Nodes/<names_path:node_names>/Leaves/<name:leaf_name>", methods=("GET",))
def editor_workspace_command(name, node_names, leaf_name):
    if node_names[0] != WorkspaceManager.COMMAND_TREE_ROOT_NAME:
        raise exceptions.ResourceNotFind("Command not exist")
    node_names = node_names[1:]

    manager = WorkspaceManager(name)
    manager.load()
    leaf = manager.find_command_tree_leaf(*node_names, leaf_name)
    if not leaf:
        raise exceptions.ResourceNotFind("Command not exist")

    # get the command configuration
    cfg_editor = manager.load_cfg_editor_by_command(leaf)
    command = cfg_editor.find_command(*leaf.names)
    result = command.to_primitive()

    del result['name']
    result['names'] = leaf.names
    return jsonify(result)


@bp.route("/Workspaces/<name>/CommandTree/Nodes/<names_path:node_names>/Leaves/<name:leaf_name>/Rename", methods=("POST",))
def editor_workspace_command_rename(name, node_names, leaf_name):
    if node_names[0] != WorkspaceManager.COMMAND_TREE_ROOT_NAME:
        raise exceptions.ResourceNotFind("Command not exist")
    node_names = node_names[1:]

    manager = WorkspaceManager(name)
    manager.load()
    if not manager.find_command_tree_leaf(*node_names, leaf_name):
        raise exceptions.ResourceNotFind("Command not exist")

    data = request.get_json()
    new_name = data.get("name", None)
    if not new_name or not isinstance(new_name, str):
        raise exceptions.InvalidAPIUsage("Invalid request")

    new_leaf_names = new_name.split(' ')
    manager.rename_command_tree_leaf(*node_names, leaf_name, new_leaf_names=new_leaf_names)
    manager.save()
    return "", 200


# command tree resource operations
@bp.route("/Workspaces/<name>/CommandTree/Nodes/<names_path:node_names>/AddSwagger", methods=("POST",))
def editor_workspace_tree_node_resources(name, node_names):
    if node_names[0] != WorkspaceManager.COMMAND_TREE_ROOT_NAME:
        raise exceptions.ResourceNotFind("Command group not exist")
    node_names = node_names[1:]

    manager = WorkspaceManager(name)
    manager.load()
    if not manager.find_command_tree_node(*node_names):
        raise exceptions.ResourceNotFind("Command group not exist")

    # add new resource
    data = request.get_json()
    if not isinstance(data, dict):
        raise exceptions.InvalidAPIUsage("Invalid request")

    try:
        mod_names = data['module']
        version = data['version']
        resource_ids = data['resources']
    except KeyError:
        raise exceptions.InvalidAPIUsage("Invalid request")

    manager.add_new_resources_by_swagger(
        mod_names=mod_names,
        version=version,
        resource_ids=resource_ids,
        *node_names
    )
    manager.save()
    return "", 200


@bp.route("/Workspaces/<name>/CommandTree/Nodes/<names_path:node_names>/Resources", methods=("GET",))
def editor_workspace_resources(name, node_names):
    if node_names[0] != WorkspaceManager.COMMAND_TREE_ROOT_NAME:
        raise exceptions.ResourceNotFind("Command group not exist")
    node_names = node_names[1:]

    manager = WorkspaceManager(name)
    manager.load()
    if not manager.find_command_tree_node(*node_names):
        raise exceptions.ResourceNotFind("Command group not exist")

    resources = manager.get_resources(*node_names)

    result = [r.to_primitive() for r in resources]
    return jsonify(result)


@bp.route("/Workspaces/<name>/Resources/Merge", methods=("Post",))
def editor_workspace_resources_merge(name):
    manager = WorkspaceManager(name)
    manager.load()
    data = request.get_json()
    if "mainResource" not in data or "plusResource" not in data:
        raise exceptions.InvalidAPIUsage("Invalid request")
    main_resource_id = data["mainResource"]["resourceId"]
    main_resource_version = data["mainResource"]["version"]
    plus_resource_id = data["plusResource"]["resourceId"]
    plus_resource_version = data["plusResource"]["version"]
    if not manager.merge_resources(main_resource_id, main_resource_version, plus_resource_id, plus_resource_version):
        raise exceptions.ResourceConflict("Cannot merge resources")
    manager.save()
    return "", 200


@bp.route("/Workspaces/<name>/Resources/<base64:resource_id>/V/<base64:version>", methods=("DELETE",))
def editor_workspace_resource(name, resource_id, version):
    manager = WorkspaceManager(name)
    manager.load()
    if not manager.remove_resource(resource_id, version):
        return "", 204
    manager.save()
    return "", 200


@bp.route("/Workspaces/<name>/CommandTree/Nodes/<names_path:node_names>/Resources/ReloadSwagger", methods=("POST",))
def editor_workspace_resource_reload_swagger(name, node_names):
    # update resource by reloading swagger
    data = request.get_json()
    # data = (resource_id, swagger_version)
    # TODO:
    raise NotImplementedError()


@bp.route("/Workspaces/<name>/CommandTree/Nodes/<names_path:node_names>/Try", methods=("POST",))
def editor_workspace_try_command_group(name, node_names):
    if node_names[0] != WorkspaceManager.COMMAND_TREE_ROOT_NAME:
        raise exceptions.ResourceNotFind("Command group not exist")
    node_names = node_names[1:]

    manager = WorkspaceManager(name)
    manager.load()
    if not manager.find_command_tree_node(*node_names):
        raise exceptions.ResourceNotFind("Command group not exist")

    # try sub commands by installed as a try extension of cli
    raise NotImplementedError()


@bp.route("/Workspaces/<name>/CommandTree/Nodes/<names_path:node_names>/Leaves/<name:leaf_name>/Try", methods=("POST",))
def editor_workspace_try_command(name, node_names, leaf_name):
    if node_names[0] != WorkspaceManager.COMMAND_TREE_ROOT_NAME:
        raise exceptions.ResourceNotFind("Command not exist")
    node_names = node_names[1:]

    manager = WorkspaceManager(name)
    manager.load()
    if not manager.find_command_tree_leaf(*node_names, leaf_name):
        raise exceptions.ResourceNotFind("Command not exist")

    # try command by installed as a try extension of cli
    raise NotImplementedError()
