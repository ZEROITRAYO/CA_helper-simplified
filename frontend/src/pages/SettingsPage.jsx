import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  errorMessage,
  markNotificationRead,
  NOTIFICATIONS_KEY,
  saveSettings,
  SETTINGS_KEY,
  useNotifications,
  useSettings,
} from "@/api";
import { Pager, QueryStatus } from "@/components/shared";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui";
import { formatDateTime } from "@/lib";

/** /business/settings and /ca/settings: my notifications and the email switch. */
export function SettingsPage() {
  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">Notification settings</h1>
      <NotificationList />
      <EmailSwitch />
    </div>
  );
}

// --- NotificationList --------------------------------------------------------------------------

// Newest first; unread ones are bold. Clicking one opens it like an email and marks it read.
function NotificationList() {
  const [page, setPage] = useState(1);
  const [opened, setOpened] = useState(null);
  const notifications = useNotifications(page);
  const queryClient = useQueryClient();

  async function open(entry) {
    setOpened(entry);
    if (entry.read_at === null) {
      try {
        await markNotificationRead(entry.id);
        queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
      } catch {
        // It stays bold and is marked read the next time it is opened.
      }
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Inbox</CardTitle>
        <CardDescription>Click a notification to read it.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <QueryStatus query={notifications} />
        {notifications.isSuccess && notifications.data.items.length === 0 && (
          <p className="text-sm text-muted-foreground">No notifications yet.</p>
        )}
        {notifications.isSuccess && notifications.data.items.length > 0 && (
          <ul className="divide-y rounded-md border">
            {notifications.data.items.map((entry) => (
              <li key={entry.id}>
                <button
                  type="button"
                  onClick={() => open(entry)}
                  className={
                    "flex w-full items-baseline justify-between gap-4 px-3 py-2 text-left text-sm hover:bg-muted " +
                    (entry.read_at === null ? "font-bold" : "text-muted-foreground")
                  }
                >
                  <span className="truncate">{entry.title}</span>
                  <span className="shrink-0 text-xs">{formatDateTime(entry.created_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {notifications.isSuccess && <Pager data={notifications.data} onPage={setPage} />}
      </CardContent>
      {opened && <NotificationView entry={opened} onClose={() => setOpened(null)} />}
    </Card>
  );
}

// One notification on top of the page, like an opened email.
function NotificationView({ entry, onClose }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-label={entry.title}
        className="w-full max-w-lg space-y-4 rounded-lg bg-background p-6 shadow-lg"
        onClick={(event) => event.stopPropagation()} // a click inside does not close it
      >
        <div className="space-y-1 border-b pb-3">
          <h2 className="text-lg font-semibold">{entry.title}</h2>
          <p className="text-xs text-muted-foreground">{formatDateTime(entry.created_at)}</p>
        </div>
        <p className="text-sm whitespace-pre-wrap">{entry.body}</p>
        <div className="flex justify-end">
          <Button onClick={onClose}>Close</Button>
        </div>
      </div>
    </div>
  );
}

// --- EmailSwitch -------------------------------------------------------------------------------

function EmailSwitch() {
  const settings = useSettings();
  const queryClient = useQueryClient();
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  async function toggle() {
    setError(null);
    setSaving(true);
    try {
      const saved = await saveSettings(!settings.data.email_notifications);
      queryClient.setQueryData(SETTINGS_KEY, saved);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Emails</CardTitle>
        <CardDescription>
          Every notification appears in the inbox above. Choose whether they are also emailed to
          you.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <QueryStatus query={settings} />
        {settings.isSuccess && (
          <label className="flex items-start gap-3 text-sm">
            <input
              type="checkbox"
              className="mt-1"
              checked={settings.data.email_notifications}
              disabled={saving}
              onChange={toggle}
            />
            <span>
              Email me my notifications
              <span className="block text-xs text-muted-foreground">
                Deadline reminders, overdue filings, document requests, CA request updates and
                rule changes. Login and password codes are always emailed.
              </span>
            </span>
          </label>
        )}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
