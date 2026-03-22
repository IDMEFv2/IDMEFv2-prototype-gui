from prewikka import pluginmanager, version

from .inputplugin import InputPluginView


class InputPlugin(pluginmanager.PluginPreload): 
    plugin_name = "InputPlugin"
    plugin_author = version.__author__
    plugin_license = version.__license__
    plugin_version = version.__version__
    plugin_copyright = version.__copyright__
    plugin_description = N_("Input Plugin")
    plugin_classes = [InputPluginView]
    plugin_database_branch = version.__branch__
    plugin_database_version = "0"
