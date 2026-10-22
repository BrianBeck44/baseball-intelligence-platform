import {
  KeyboardEvent,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";

interface SearchableSelectOption {
  value: string;
  label: string;
}

interface SearchableSelectProps {
  id: string;
  label: string;
  value: string;
  options: SearchableSelectOption[];
  disabled?: boolean;
  required?: boolean;
  searchValue: string;
  onSearchChange: (value: string) => void;
  onChange: (value: string) => void;
  placeholder: string;
  searchPlaceholder: string;
  emptyMessage: string;
}

export function SearchableSelect({
  id,
  label,
  value,
  options,
  disabled = false,
  required = false,
  searchValue,
  onSearchChange,
  onChange,
  placeholder,
  searchPlaceholder,
  emptyMessage,
}: SearchableSelectProps) {
  const listId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);

  const query = searchValue.trim().toLowerCase();
  const filtered = useMemo(
    () =>
      options.filter((option) =>
        option.label.toLowerCase().includes(query),
      ),
    [options, query],
  );
  const selected = options.find((option) => option.value === value);
  const showMenu = open && !disabled;
  const highlighted = filtered[highlight];
  const activeOptionId =
    showMenu && highlighted ? `${listId}-opt-${highlighted.value}` : undefined;

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  useEffect(() => {
    setHighlight(0);
  }, [searchValue, options]);

  useEffect(() => {
    if (!activeOptionId) {
      return;
    }
    document.getElementById(activeOptionId)?.scrollIntoView({
      block: "nearest",
    });
  }, [activeOptionId]);

  function handleInputChange(text: string) {
    onSearchChange(text);
    if (selected && selected.label !== text) {
      onChange("");
    }
    setOpen(true);
  }

  function selectOption(option: SearchableSelectOption) {
    onSearchChange(option.label);
    onChange(option.value);
    setOpen(false);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (disabled) {
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setHighlight((index) =>
        filtered.length === 0 ? 0 : Math.min(index + 1, filtered.length - 1),
      );
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      setHighlight((index) => Math.max(index - 1, 0));
      return;
    }

    if (event.key === "Enter" && open && highlighted) {
      event.preventDefault();
      selectOption(highlighted);
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
    }
  }

  return (
    <div className="searchable-select" ref={containerRef}>
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="text"
        role="combobox"
        aria-expanded={showMenu}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={activeOptionId}
        aria-haspopup="listbox"
        autoComplete="off"
        disabled={disabled}
        required={required && value === ""}
        placeholder={disabled ? placeholder : searchPlaceholder}
        value={searchValue}
        onChange={(event) => handleInputChange(event.target.value)}
        onFocus={() => {
          if (!disabled) {
            setOpen(true);
          }
        }}
        onKeyDown={handleKeyDown}
      />
      {showMenu ? (
        <ul id={listId} role="listbox" className="searchable-select-menu">
          {filtered.length === 0 ? (
            <li className="searchable-select-empty" role="presentation">
              {emptyMessage}
            </li>
          ) : (
            filtered.map((option, index) => (
              <li
                key={option.value}
                id={`${listId}-opt-${option.value}`}
                role="option"
                aria-selected={option.value === value}
                className={
                  index === highlight ? "searchable-select-option is-active" : "searchable-select-option"
                }
                onMouseDown={(event) => {
                  event.preventDefault();
                  selectOption(option);
                }}
                onMouseEnter={() => setHighlight(index)}
              >
                {option.label}
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}
