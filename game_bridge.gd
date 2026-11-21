var _assistant_server := TCPServer.new()
var _assistant_clients: Array[StreamPeerTCP] = []
var _assistant_listen_status := ERR_UNAVAILABLE
var _assistant_last_magnifier_count := -1
var _assistant_last_beer_count := -1
var _assistant_last_player_inverter_count := -1
var _assistant_last_dealer_inverter_count := -1
var _assistant_last_shell_count := -1
var _assistant_player_knows_current_shell := false
var _assistant_current_shell_inverted_unknown := false
var _assistant_public_live_shells := 0
var _assistant_public_blank_shells := 0
var _assistant_hud_action: Label
var _assistant_hud_detail: Label
var _assistant_hud_font: SystemFont
var _assistant_hud_panel: PanelContainer
var _assistant_hud_resize_grip: Label
var _assistant_hud_resize_active := false
var _assistant_hud_resize_origin := Vector2.ZERO
var _assistant_hud_resize_initial_size := Vector2.ZERO

func _assistant_start_server():
	_assistant_create_hud()
	_assistant_listen_status = _assistant_server.listen(47891, "127.0.0.1")

func _assistant_create_hud():
	_assistant_hud_font = SystemFont.new()
	_assistant_hud_font.font_names = PackedStringArray(["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Arial"])
	_assistant_hud_font.antialiasing = TextServer.FONT_ANTIALIASING_GRAY
	_assistant_hud_font.hinting = TextServer.HINTING_NORMAL
	_assistant_hud_font.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	_assistant_hud_font.oversampling = 2.0
	_assistant_hud_font.allow_system_fallback = true
	var layer = CanvasLayer.new()
	layer.name = "AssistantHudLayer"
	layer.layer = 100
	get_tree().root.add_child(layer)
	_assistant_hud_panel = PanelContainer.new()
	_assistant_hud_panel.name = "AssistantHudPanel"
	_assistant_hud_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var viewport_width = get_viewport().get_visible_rect().size.x
	var panel_width = maxf(220.0, minf(380.0, viewport_width - 44.0))
	_assistant_hud_panel.position = Vector2(22.0, 22.0)
	_assistant_hud_panel.size = Vector2(panel_width, 112.0)
	_assistant_hud_panel.custom_minimum_size = Vector2(panel_width, 112.0)
	var panel_style = StyleBoxFlat.new()
	panel_style.bg_color = Color(0.018, 0.032, 0.036, 0.9)
	panel_style.border_color = Color(1.0, 1.0, 1.0, 0.86)
	panel_style.border_width_left = 2
	panel_style.border_width_top = 2
	panel_style.border_width_right = 2
	panel_style.border_width_bottom = 2
	panel_style.corner_radius_top_left = 0
	panel_style.corner_radius_top_right = 0
	panel_style.corner_radius_bottom_left = 0
	panel_style.corner_radius_bottom_right = 0
	panel_style.shadow_color = Color(1.0, 1.0, 1.0, 0.0)
	panel_style.shadow_size = 0
	panel_style.shadow_offset = Vector2(0.0, 2.0)
	panel_style.anti_aliasing = true
	panel_style.content_margin_left = 15.0
	panel_style.content_margin_top = 11.0
	panel_style.content_margin_right = 15.0
	panel_style.content_margin_bottom = 11.0
	_assistant_hud_panel.add_theme_stylebox_override("panel", panel_style)
	layer.add_child(_assistant_hud_panel)
	var content = VBoxContainer.new()
	content.mouse_filter = Control.MOUSE_FILTER_IGNORE
	content.add_theme_constant_override("separation", 4)
	_assistant_hud_panel.add_child(content)
	var header = HBoxContainer.new()
	header.mouse_filter = Control.MOUSE_FILTER_IGNORE
	header.add_theme_constant_override("separation", 8)
	content.add_child(header)
	var accent = ColorRect.new()
	accent.mouse_filter = Control.MOUSE_FILTER_IGNORE
	accent.color = Color(1.0, 1.0, 1.0, 1.0)
	accent.custom_minimum_size = Vector2(3.0, 14.0)
	header.add_child(accent)
	var title = Label.new()
	title.mouse_filter = Control.MOUSE_FILTER_IGNORE
	title.text = "萌萌刻"
	title.add_theme_font_override("font", _assistant_hud_font)
	title.add_theme_font_size_override("font_size", 12)
	title.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0, 0.84))
	header.add_child(title)
	_assistant_hud_action = Label.new()
	_assistant_hud_action.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_assistant_hud_action.text = "等待助手连接"
	_assistant_hud_action.add_theme_font_override("font", _assistant_hud_font)
	_assistant_hud_action.add_theme_font_size_override("font_size", 20)
	_assistant_hud_action.add_theme_color_override("font_color", Color(0.96, 1.0, 0.98, 1.0))
	_assistant_hud_action.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	content.add_child(_assistant_hud_action)
	_assistant_hud_detail = Label.new()
	_assistant_hud_detail.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_assistant_hud_detail.text = "等待游戏状态"
	_assistant_hud_detail.add_theme_font_override("font", _assistant_hud_font)
	_assistant_hud_detail.add_theme_font_size_override("font_size", 12)
	_assistant_hud_detail.add_theme_color_override("font_color", Color(0.86, 0.88, 0.9, 1.0))
	_assistant_hud_detail.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	content.add_child(_assistant_hud_detail)
	_assistant_hud_resize_grip = Label.new()
	_assistant_hud_resize_grip.text = "↘"
	_assistant_hud_resize_grip.position = _assistant_hud_panel.position + _assistant_hud_panel.size - Vector2(20.0, 20.0)
	_assistant_hud_resize_grip.size = Vector2(20.0, 20.0)
	_assistant_hud_resize_grip.mouse_filter = Control.MOUSE_FILTER_STOP
	_assistant_hud_resize_grip.mouse_default_cursor_shape = Control.CURSOR_BDIAGSIZE
	_assistant_hud_resize_grip.add_theme_font_override("font", _assistant_hud_font)
	_assistant_hud_resize_grip.add_theme_font_size_override("font_size", 13)
	_assistant_hud_resize_grip.add_theme_color_override("font_color", Color(1.0, 1.0, 1.0, 0.82))
	_assistant_hud_resize_grip.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_assistant_hud_resize_grip.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_assistant_hud_resize_grip.gui_input.connect(_assistant_begin_hud_resize.bind(_assistant_hud_panel))
	layer.add_child(_assistant_hud_resize_grip)

func _assistant_set_advice(payload: String):
	if _assistant_hud_action == null or _assistant_hud_detail == null:
		return
	var separator = payload.find("\n")
	if separator < 0:
		_assistant_hud_action.text = payload
		_assistant_hud_detail.text = ""
		return
	_assistant_hud_action.text = payload.substr(0, separator)
	_assistant_hud_detail.text = payload.substr(separator + 1)

func _assistant_begin_hud_resize(event: InputEvent, panel: PanelContainer):
	if not (event is InputEventMouseButton):
		return
	var button_event = event as InputEventMouseButton
	if button_event.button_index != MOUSE_BUTTON_LEFT:
		return
	if button_event.pressed:
		_assistant_hud_resize_active = true
		_assistant_hud_resize_origin = get_viewport().get_mouse_position()
		_assistant_hud_resize_initial_size = panel.size
	else:
		_assistant_hud_resize_active = false
	_assistant_hud_resize_grip.accept_event()

func _assistant_update_hud_resize():
	if not _assistant_hud_resize_active:
		return
	if not Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
		_assistant_hud_resize_active = false
		return
	var viewport_size = get_viewport().get_visible_rect().size
	var max_width = maxf(220.0, viewport_size.x - _assistant_hud_panel.position.x - 12.0)
	var max_height = maxf(112.0, viewport_size.y - _assistant_hud_panel.position.y - 12.0)
	var mouse_delta = get_viewport().get_mouse_position() - _assistant_hud_resize_origin
	var resized = Vector2(
		clampf(_assistant_hud_resize_initial_size.x + mouse_delta.x, 220.0, max_width),
		clampf(_assistant_hud_resize_initial_size.y + mouse_delta.y, 112.0, max_height)
	)
	_assistant_hud_panel.custom_minimum_size = resized
	_assistant_hud_panel.size = resized
	_assistant_hud_resize_grip.position = _assistant_hud_panel.position + resized - _assistant_hud_resize_grip.size

func _assistant_poll():
	_assistant_update_hud_resize()
	if _assistant_listen_status != OK:
		return
	if _assistant_server.is_connection_available():
		_assistant_clients.append(_assistant_server.take_connection())
	for i in range(_assistant_clients.size() - 1, -1, -1):
		var peer = _assistant_clients[i]
		if peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
			_assistant_clients.remove_at(i)
			continue
		var available = peer.get_available_bytes()
		if available <= 0:
			continue
		var packet = peer.get_data(available)
		if packet[0] == OK:
			var request = packet[1].get_string_from_utf8().strip_edges()
			if request == "STATE":
				peer.put_data(JSON.stringify(_assistant_state()).to_utf8_buffer())
			elif request.begins_with("ADVICE\t"):
				_assistant_set_advice(request.substr(7))
				peer.put_data("OK".to_utf8_buffer())
		peer.disconnect_from_host()
		_assistant_clients.remove_at(i)

func _assistant_track_player_knowledge():
	var magnifier_count = 0
	var beer_count = 0
	var player_inverter_count = 0
	var dealer_inverter_count = 0
	for item in itemManager.amounts.array_amounts:
		if item.itemName.to_lower() == "magnifying glass":
			magnifier_count = item.amount_player
		elif item.itemName.to_lower() == "beer":
			beer_count = item.amount_player
		elif item.itemName.to_lower() == "inverter":
			player_inverter_count = item.amount_player
			dealer_inverter_count = item.amount_dealer
	var shell_count = shellSpawner.sequenceArray.size()
	var actual_live_shells = shellSpawner.sequenceArray.count("live")
	var actual_blank_shells = shellSpawner.sequenceArray.count("blank")
	if _assistant_last_magnifier_count < 0:
		_assistant_last_magnifier_count = magnifier_count
		_assistant_last_beer_count = beer_count
		_assistant_last_player_inverter_count = player_inverter_count
		_assistant_last_dealer_inverter_count = dealer_inverter_count
		_assistant_last_shell_count = shell_count
		_assistant_public_live_shells = actual_live_shells
		_assistant_public_blank_shells = actual_blank_shells
		return
	var shell_delta = shell_count - _assistant_last_shell_count
	var inverter_uses = _assistant_last_player_inverter_count - player_inverter_count
	inverter_uses += _assistant_last_dealer_inverter_count - dealer_inverter_count
	if shell_delta > 0:
		_assistant_public_live_shells = actual_live_shells
		_assistant_public_blank_shells = actual_blank_shells
		_assistant_current_shell_inverted_unknown = false
		_assistant_player_knows_current_shell = false
	elif shell_delta < 0:
		_assistant_public_live_shells = actual_live_shells
		_assistant_public_blank_shells = actual_blank_shells
		_assistant_current_shell_inverted_unknown = false
		_assistant_player_knows_current_shell = false
	elif inverter_uses > 0:
		if _assistant_player_knows_current_shell:
			_assistant_public_live_shells = actual_live_shells
			_assistant_public_blank_shells = actual_blank_shells
			_assistant_current_shell_inverted_unknown = false
		else:
			_assistant_current_shell_inverted_unknown = not _assistant_current_shell_inverted_unknown if inverter_uses % 2 == 1 else _assistant_current_shell_inverted_unknown
	if magnifier_count < _assistant_last_magnifier_count:
		_assistant_player_knows_current_shell = true
		_assistant_public_live_shells = actual_live_shells
		_assistant_public_blank_shells = actual_blank_shells
		_assistant_current_shell_inverted_unknown = false
	if beer_count < _assistant_last_beer_count:
		_assistant_player_knows_current_shell = false
	_assistant_last_magnifier_count = magnifier_count
	_assistant_last_beer_count = beer_count
	_assistant_last_player_inverter_count = player_inverter_count
	_assistant_last_dealer_inverter_count = dealer_inverter_count
	_assistant_last_shell_count = shell_count

func _assistant_state():
	_assistant_track_player_knowledge()
	var player_items = {}
	var dealer_items = {}
	for item in itemManager.amounts.array_amounts:
		var name = item.itemName.to_lower()
		if item.amount_player > 0:
			player_items[name] = item.amount_player
		if item.amount_dealer > 0:
			dealer_items[name] = item.amount_dealer
	var player_can_act = deskUI_parent.visible and deskUI_shotgun.visible
	var phase = "busy"
	if health_player <= 0:
		phase = "player_dead"
	elif health_opponent <= 0:
		phase = "dealer_dead"
	elif shellSpawner.sequenceArray.is_empty():
		phase = "reload"
	elif player_can_act:
		phase = "player_turn"
	elif dealerAI.dealerHoldingShotgun or dealerAI.mainLoopFinished:
		phase = "dealer_turn"
	return {
		"phase": phase,
		"player_can_act": player_can_act,
		"player_hp": health_player,
		"dealer_hp": health_opponent,
		"max_hp": roundArray[currentRound].startingHealth if currentRound >= 0 and currentRound < roundArray.size() else 0,
		"round_index": currentRound,
		"round_count": roundArray.size(),
		"batch_index": playerData.currentBatchIndex,
		"live_shells_remaining": _assistant_public_live_shells,
		"blank_shells_remaining": _assistant_public_blank_shells,
		"current_shell_known": _assistant_player_knows_current_shell,
		"current_shell": shellSpawner.sequenceArray[0] if _assistant_player_knows_current_shell and not shellSpawner.sequenceArray.is_empty() else "",
		"current_shell_inverted_unknown": _assistant_current_shell_inverted_unknown,
		"player_items": player_items,
		"dealer_items": dealer_items,
		"current_shotgun_damage": currentShotgunDamage,
		"dealer_cuffed": dealerCuffed,
		"dealer_about_to_break_free": dealerAI.dealerAboutToBreakFree,
		"player_cuffed": playerCuffed,
		"player_about_to_break_free": playerAboutToBreakFree,
		"endless": endless,
		"true_death": trueDeathActive,
		"wire_cut_player": wireIsCut_player,
		"wire_cut_dealer": wireIsCut_dealer
	}
