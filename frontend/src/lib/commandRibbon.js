/**
 * Shared command/ribbon contract.
 *
 * @typedef {Object} RibbonCommand
 * @property {string} id Stable command id.
 * @property {string} label Customer-facing command label.
 * @property {React.ComponentType=} icon Lucide icon component.
 * @property {string=} to Internal route destination.
 * @property {Function=} onSelect Page action handler.
 * @property {string=} group Group id.
 * @property {string=} tooltip Tooltip or disabled explanation.
 * @property {string=} permission Required frontend permission for visibility.
 * @property {string=} entitlement Feature key for disabled/upgrade state.
 * @property {boolean|Function=} visible Boolean or predicate.
 * @property {boolean|Function=} disabled Boolean or predicate.
 * @property {string=} disabledReason Explanation for disabled commands.
 * @property {boolean=} loading Loading state.
 * @property {boolean=} active Active visual state.
 * @property {string=} badge Optional short badge.
 * @property {RibbonCommand[]=} children Dropdown child commands.
 * @property {number=} responsivePriority Lower numbers stay visible first.
 * @property {string=} keyboardShortcut Optional visible shortcut label.
 * @property {string=} analyticsId Optional analytics identifier.
 * @property {string=} testId Test id.
 */

export function isCommandVisible(command, auth = {}) {
  if (!command) return false;
  const visible = typeof command.visible === "function" ? command.visible() : command.visible;
  if (visible === false) return false;
  if (command.permission && typeof auth.hasPerm === "function" && !auth.hasPerm(command.permission)) return false;
  return true;
}

export function commandDisabledState(command, entitlements = {}) {
  if (!command) return { disabled: true, reason: "Unavailable" };
  if (command.loading) return { disabled: true, reason: "Loading" };
  if (command.entitlement && entitlements[command.entitlement] === false) {
    return { disabled: true, reason: command.disabledReason || "Upgrade required" };
  }
  const disabled = typeof command.disabled === "function" ? command.disabled() : command.disabled;
  return {
    disabled: !!disabled,
    reason: disabled ? command.disabledReason || command.tooltip || "Unavailable" : null,
  };
}

export function visibleCommandGroups(groups = [], auth = {}) {
  return (groups || [])
    .map((group) => ({
      ...group,
      commands: (group.commands || [])
        .filter((command) => isCommandVisible(command, auth))
        .map((command) => ({
          ...command,
          children: command.children?.filter((child) => isCommandVisible(child, auth)),
        })),
    }))
    .filter((group) => group.commands.length > 0);
}

export function splitPrimaryAndOverflow(groups = [], maxPrimaryCommands = 12) {
  let visibleCount = 0;
  const primaryGroups = [];
  const overflowCommands = [];

  for (const group of groups) {
    const primaryCommands = [];
    const sorted = [...(group.commands || [])].sort((a, b) => (
      (a.responsivePriority ?? 50) - (b.responsivePriority ?? 50)
    ));
    for (const command of sorted) {
      if (command.overflow || visibleCount >= maxPrimaryCommands) {
        overflowCommands.push({ ...command, groupLabel: group.label });
      } else {
        primaryCommands.push(command);
        visibleCount += 1;
      }
    }
    if (primaryCommands.length) primaryGroups.push({ ...group, commands: primaryCommands });
  }

  return { primaryGroups, overflowCommands };
}
