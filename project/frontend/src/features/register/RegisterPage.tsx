import { useEffect, useRef, useState } from 'react';
import { apiClient } from '../../api/client';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Modal } from '../../components/ui/modal';
import type { RegisteredItemDto } from '../../types/domain';

export function RegisterPage() {
  const [name, setName] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [items, setItems] = useState<RegisteredItemDto[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  async function load() {
    setError(null);
    try {
      setItems(await apiClient.listRegistered());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function onAdd() {
    setLoading(true);
    setError(null);
    try {
      await apiClient.addRegistered(name.trim(), files);
      setName('');
      setFiles([]);
      setModalOpen(false);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  async function onDelete(itemName: string) {
    setLoading(true);
    setError(null);
    try {
      await apiClient.removeRegistered(itemName);
      setDeleteTarget(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page-shell">
      <h2 className="section-title">Register</h2>

      <div className="two-pane">
        <div className="feature-card panel">
          <h3 className="panel-title">Reference Management</h3>
          <p className="panel-subtitle">Use custom modal flow to keep interaction consistent.</p>

          <div className="result-box">
            <p><strong>Total items</strong>: {items.length}</p>
            <p><strong>Status</strong>: {loading ? 'processing...' : 'ready'}</p>
          </div>

          <div className="btn-row" style={{ marginTop: 12 }}>
            <Button className="w-full btn-intent-search" onClick={() => setModalOpen(true)} disabled={loading}>
              Open Add Item Modal
            </Button>
          </div>

          {error && <p className="error">{error}</p>}
        </div>

        <div className="feature-card panel">
          <h3 className="panel-title">Registered Items</h3>
          <div className="result-list list-scroll">
            {items.length === 0 ? (
              <p className="empty-state">No registered items.</p>
            ) : (
              items.map((x) => (
                <div className="result-box result-inline" key={x.name}>
                  <span>{x.name}</span>
                  <Button className="btn-intent-delete" variant="outline" onClick={() => setDeleteTarget(x.name)} disabled={loading}>
                    Delete
                  </Button>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="Add Reference Item">
        <div className="field-row">
          <Label htmlFor="register-name-modal">Item name</Label>
          <Input
            id="register-name-modal"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. my key"
          />
        </div>

        <div className="field-row">
          <Label>Item images</Label>
          <input
            ref={fileRef}
            type="file"
            multiple
            accept="image/*"
            className="hidden-file"
            onChange={(e) => setFiles(Array.from(e.currentTarget.files ?? []))}
          />
          <Button className="btn-intent-preview" type="button" variant="outline" onClick={() => fileRef.current?.click()}>
            Select Images
          </Button>
          <p className="muted">{files.length} file(s) selected</p>
          {files.length > 0 && (
            <div className="file-chip-list">
              {files.map((f, i) => (
                <div key={`${f.name}-${i}`} className="file-chip">
                  <span>{f.name}</span>
                  <button
                    type="button"
                    className="file-chip-remove"
                    onClick={() => setFiles((prev) => prev.filter((_, idx) => idx !== i))}
                    aria-label="remove-file"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="btn-row">
          <Button className="w-full btn-intent-start" onClick={onAdd} disabled={loading || !name.trim() || files.length === 0}>
            {loading ? 'Saving...' : 'Save Item'}
          </Button>
          <Button className="w-full btn-intent-cancel" type="button" variant="ghost" onClick={() => setModalOpen(false)}>
            Cancel
          </Button>
        </div>
      </Modal>

      <Modal
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Delete Registered Item"
      >
        <p className="muted" style={{ marginBottom: 12 }}>
          Delete <strong>{deleteTarget ?? ''}</strong>? This action cannot be undone.
        </p>
        <div className="btn-row">
          <Button
            className="w-full btn-intent-delete"
            variant="outline"
            onClick={() => (deleteTarget ? onDelete(deleteTarget) : undefined)}
            disabled={loading || !deleteTarget}
          >
            {loading ? 'Deleting...' : 'Delete'}
          </Button>
          <Button className="w-full btn-intent-cancel" type="button" variant="ghost" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
        </div>
      </Modal>
    </section>
  );
}
