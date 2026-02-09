import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import Home from "../page";

afterEach(() => {
  vi.restoreAllMocks();
});

const createFile = () =>
  new File(["%PDF-1.4 test"], "test.pdf", { type: "application/pdf" });

const mockSuccessfulFlow = () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ brief: "Mock brief" }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        worksheet: {
          title: "Mock Exam",
          subject: "Science",
          target_level: "Grade 7",
          items: [],
        },
        new_topics: [],
      }),
    })
    .mockResolvedValueOnce({
      ok: true,
      blob: async () => new Blob(["docx"], { type: "application/octet-stream" }),
    });

  vi.stubGlobal("fetch", fetchMock);
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock");

  return fetchMock;
};

describe("Exam Gen Dashboard", () => {
  it("syncs exam type to analyze and generate requests", async () => {
    const fetchMock = mockSuccessfulFlow();
    const { container } = render(<Home />);

    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    const select = screen.getByRole("combobox");
    const tenButtons = screen.getAllByRole("button", { name: "10 ข้อ" });
    const startButton = screen.getAllByRole("button", {
      name: /start generation/i,
    })[0];

    fireEvent.click(tenButtons[0]);
    fireEvent.change(select, { target: { value: "subjective" } });
    fireEvent.change(fileInput, { target: { files: [createFile()] } });

    fireEvent.click(startButton);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(3);
    });

    const analyzeForm = fetchMock.mock.calls[0][1]?.body as FormData;
    const generateForm = fetchMock.mock.calls[1][1]?.body as FormData;

    expect(analyzeForm.get("exam_type")).toBe("subjective");
    expect(generateForm.get("exam_type")).toBe("subjective");
  });

  it("updates batch progress and finishes on success", async () => {
    mockSuccessfulFlow();
    const { container } = render(<Home />);

    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    const tenButton = screen.getAllByRole("button", { name: "10 ข้อ" })[0];
    const startButton = screen.getAllByRole("button", {
      name: /start generation/i,
    })[0];

    fireEvent.click(tenButton);
    fireEvent.change(fileInput, { target: { files: [createFile()] } });
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(screen.getByText("1/1 batches")).toBeInTheDocument();
    });

    const statusEntries = screen.getAllByText(/status:/i);
    const statusTexts = statusEntries.map((node) => node.textContent ?? "");
    expect(statusTexts.some((text) => text.includes("Done"))).toBe(true);
  });

  it("shows error when batch generation fails", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ brief: "Mock brief" }),
      })
      .mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: "เจนข้อสอบบางรอบไม่สำเร็จ" }),
      });

    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<Home />);
    const fileInput = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    const startButton = screen.getAllByRole("button", {
      name: /start generation/i,
    })[0];

    fireEvent.change(fileInput, { target: { files: [createFile()] } });
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(screen.getByText("เจนข้อสอบบางรอบไม่สำเร็จ")).toBeInTheDocument();
    });
  });
});
