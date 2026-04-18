import React, { useEffect, useMemo, useState } from "react";
import {
  Table,
  Space,
  message,
  Button,
  Select,
  Input,
  Modal,
  Spin,
  Dropdown,
  MenuProps,
} from "antd";
import { useStores } from "../../../hooks/useStores";
import { Link, useNavigate } from "react-router-dom";
import {
  useCheckoutServiceCreateCheckoutSessionApiV1CheckoutCreateCheckoutSessionPost,
  useCvServiceGenerateCvDownloadReportApiV1CvGenerateReportPost,
  useCvServiceGenerateCvReportApiV1CvGenerateReportPost,
  useCvServiceGenerateSaudiReportApiV1CvGenerateSaudiPost,
  usePromotionServiceReadPackagePurchasePostApiV1CompanyUrlInfoRequest,
  useReserveServiceAcceptDeclineReserveApiV1ReservePatch,
  useReserveServiceReadPackagePurchasePostApiV1CompanyUrlInfoRequest,
  useReserveServiceViewMyReservesApiV1ReserveMyReservesPost,
  useReserveServiceViewReserveHistoryApiV1ReserveHistoryPost,
  useStatServiceGetNonEmployeeDashboardDataApiV1StatPost,
} from "../../../api/queries";
import {
  TransferStatusSchema,
  ReserveReadSchema,
  BatchReserveReadSchema,
  CheckoutTypeSchema,
  UserRoleSchema,
} from "../../../api/requests";
import { tw } from "typewind";
import { GoTriangleUp } from "react-icons/go";
import StatusCard from "../../../components/common/StatusCard";
import { DownOutlined, RightOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import RejectReasonModal from "../../../components/common/RejectReasonModal";
import dayjs from "dayjs";
import usePagination from "../../../hooks/usePagination";
import StatSection from "../../../components/common/StatSection";
import TableSection from "../../../components/common/TableSection";
import { ExpandIcon } from "../../../components/common/ExportIcon";
import axios from "axios";
import { extractToken } from "../../../Utils/extractToken";
import { toast, ToastContainer } from "react-toastify";

const { Option } = Select;



interface BuyerRequest {
  id: number; // might be returned in real API
  cv_id: string;
  buyer_id: string;
  requested: boolean;
  status: string;
}



const RecruitmentReserveDash = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [buyerRequests, setBuyerRequests] = useState<BuyerRequest[]>([]);

  const cachedUserInfo = JSON.parse(localStorage.getItem("userInfo") || "{}");
  const recruiter_id = cachedUserInfo?.id;
  const [selectedRecord, setSelectedRecord] = useState<any>(null);
  const [withPassport, setWithPassport] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [acceptedReserves, setAcceptedReserves] = useState<any[]>([]);
  const [Reserves, setReserves] = useState<any[]>([]);
  const [acceptedLoading, setAcceptedLoading] = useState(false);
  const [payingId, setPayingId] = useState<number | null>(null);
  const [SecondpayingId, setSecondPayingId] = useState<number | null>(null);
  const [checkoutId, setCheckoutId] = useState<string | null>(null);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [SecondcheckoutId, setSecondCheckoutId] = useState<string | null>(null);
  const [showSecondPaymentModal, setShowSecondPaymentModal] = useState(false);
  // Fetch buyer requests for recruiter
  
  const fetchBuyerRequests = async () => {
    try {
      setLoading(true);
      const res = await fetch(
         `${import.meta.env.VITE_BASE_URL}/api/v1/recruiter_reserve_employeer/recruitment/pending-reserves/employer-request?recruiter_id=${recruiter_id}`         
        );
      const data = await res.json();

            if (res.ok) {
        const mapped = data.data.map((item: any, idx: number) => ({
          id: item.id || idx + 1,
          recruitment_id: item.recruitment_id,
          agent_id: item.agent_id,
          agent_name: item.agent_name,
          employee_id: item.employee_id,
          status: item.status,
          created_at: item.created_at,
        }));
          setBuyerRequests(mapped);
     
      } else {
        message.error(data.message || "Failed to fetch buyer requests");
      }
    } catch (err) {
      console.error(err);
      message.error("Error fetching buyer requests");
    } finally {
      setLoading(false);
    }
  };


  /* ---------------- LOAD HYPERPAY WIDGET ---------------- */
  
  useEffect(() => {
    if (!checkoutId || !showPaymentModal) return;
  
    const existing = document.getElementById("hyperpay-script");
    if (existing) existing.remove();
  
    const script = document.createElement("script");
    script.id = "hyperpay-script";
    script.src = `https://eu-test.oppwa.com/v1/paymentWidgets.js?checkoutId=${checkoutId}`;
  
    script.async = true;
  
    document.body.appendChild(script);
  
    return () => {
      script.remove();
    };
  }, [checkoutId, showPaymentModal]);
  
  
    useEffect(() => {
    if (!SecondcheckoutId || !showSecondPaymentModal) return;
  
    const existing = document.getElementById("hyperpay-script");
    if (existing) existing.remove();
  
    const script = document.createElement("script");
    script.id = "hyperpay-script";
    script.src = `https://eu-test.oppwa.com/v1/paymentWidgets.js?checkoutId=${SecondcheckoutId}`;
  
    script.async = true;
  
    document.body.appendChild(script);
  
    return () => {
      script.remove();
    };
  }, [SecondcheckoutId, showSecondPaymentModal]);
  
 
const fetchAcceptedReserves = async (
  recruiter_id: string,
  role: "recruiter"
) => {
  try {
    setAcceptedLoading(true);

    const token = localStorage.getItem("accessToken");
    if (!token) return;

    const response = await fetch(
      `${import.meta.env.VITE_BASE_URL}/api/v1/recruiter_reserve_employeer/selfsponsor/pending-reserves/reserves/accepted?user_id=${recruiter_id}&role=${role}`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      }
    );

    const data = await response.json();
    console.log('fetchAcceptedReserves response', data);
    if (response.ok) {
      const mapped = data.data.map((item: any) => ({
        id: item.reserve_id,
      recruitment_id: item.recruitment_id,
      agent_id: item.agent_id,
      sponsor_id: item.sponsor_id,
      cv_id: item.cv_id,
      passport_id: item.passport_id,
      status: item.status?.toUpperCase(),
      with_passport: item.with_passport,
      is_reserved: item.is_reserved === true,
      passport_number: item.passport_number,
      is_paid: item.is_paid === true,
      price: item.price,
      created_at: item.created_at,
      }));

      setAcceptedReserves(mapped);
    
    } else {
      console.error(data);
    }
  } catch (error) {
    console.error(error);
  } finally {
    setAcceptedLoading(false);
  }
};


const fetchReserves = async (
  recruiter_id: string
) => {
  try {
    setAcceptedLoading(true);
    const token = localStorage.getItem("accessToken");
    if (!token) return;
    const response = await fetch(
      `${import.meta.env.VITE_BASE_URL}/api/v1/recruiter_reserve_employeer/recruiter/transfer/requests?recruiter_id=${recruiter_id}`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      }
    )
    const data = await response.json();
    if (response.ok) {
      const mapped = data.data.map((item: any) => ({

      id: item.reserve_id,
      recruitment_id: item.to_recruitment_id,
      employee_id: item.employee_id,
      passport_number: item.passport_number,
      is_transfer_requested: item.is_reserved === true,
      is_transfer_approved: item.is_reserved === true,

      }));

      setReserves(mapped);
    
    } else {
      console.error(data);
    }
  } catch (error) {
    console.error(error);
  } finally {
    setAcceptedLoading(false);
  }
};


  const generateCvData =
    useCvServiceGenerateCvReportApiV1CvGenerateReportPost();
    const generateCvDataDownload =
    useCvServiceGenerateCvDownloadReportApiV1CvGenerateReportPost();
    
    
const handlePay = async (reserveId: number, cv_id: string) => {
  try {
    setPayingId(reserveId);

    const token = localStorage.getItem("accessToken");

    const res = await fetch(
      `${import.meta.env.VITE_BASE_URL}/api/v1/recruiter_reserve_employeer/reserve/payment/init`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          reserve_id: reserveId,
          cv_id: cv_id, // ✅ Pass CV ID for payment
        }),
      }
    );

    const data = await res.json();

    if (!res.ok) throw new Error(data.message);

    setCheckoutId(data.checkoutId);
    setShowPaymentModal(true);
  } catch (err: any) {
    message.error(err.message || "Payment failed");
  } finally {
    setPayingId(null);
  }
};


  
const handleSecondPay = async (reserveId: number) => {
  try {
    setSecondPayingId(reserveId);

    const token = localStorage.getItem("accessToken");

    const res = await fetch(
      `${import.meta.env.VITE_BASE_URL}/api/v1/recruiter_reserve_employeer/recruiter-transfer/reserve/payment/init`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          reserve_id: reserveId
        }),
      }
    );

    const data = await res.json();

    if (!res.ok) throw new Error(data.message);

    setSecondCheckoutId(data.checkoutId);
    setShowSecondPaymentModal(true);
  } catch (err: any) {
    message.error(err.message || "Payment failed");
  } finally {
    setSecondPayingId(null);
  }
};

useEffect(() => {
  if (!recruiter_id) return;

  fetchBuyerRequests();
  fetchAcceptedReserves(recruiter_id, "recruiter");
  fetchReserves(recruiter_id);
}, []);


const handleApproveSponsor = async (
    recruiter_id: string,
    withPassport: boolean
  ) => {
    try {
      setLoading(true);
  
      const res = await fetch(
        `${import.meta.env.VITE_BASE_URL}/api/v1/recruiter_reserve_employeer/recruiter/pending-reserves/employer-request/approve?recruiter_id=${recruiter_id}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            with_passport: withPassport,  // ✅ Only boolean in body
          }),
        }
      );
  
      const data = await res.json();
  
      if (res.ok) {
        message.success("Reservation approved successfully");
        fetchBuyerRequests();
      } else {
        message.error(
          data.detail || data.message || "Failed to approve reservation"
        );
      }
    } catch (error) {
      console.error(error);
      message.error("Error approving reservation");
    } finally {
      setLoading(false);
    }
  };
    

  useEffect(() => {
    fetchBuyerRequests();
  }, []);

  // Table columns
 const columns = [
      { title: t("ID"), dataIndex: "id", key: "id" },
      { title: t("sponsor"), dataIndex: "sponsor_name", key: "sponsor_name" },
      {
        title: t("Status"),
        dataIndex: "status",
        key: "status",
        render: (status: string) => (
          <span
            className={`px-2 py-1 rounded ${
              status === "ACCEPTED"
                ? "bg-green-100 text-green-600"
                : status === "REJECTED"
                ? "bg-red-100 text-red-600"
                : "bg-yellow-100 text-yellow-600"
            }`}
          >
            {status}
          </span>
        ),
      },

      {
    title: t("Actions"),
    key: "actions",
    render: (_: any, record: any) => (
      <Button
        type="primary"
        size="small"
        onClick={() => {
          setSelectedRecord(record);
          setIsModalOpen(true);
        }}
      >
        {t("Approve")}
      </Button>
    ),
  },
      {
        title: t("Created At"),
        dataIndex: "created_at",
        key: "created_at",
        render: (date: string) =>
          date ? (
            new Date(date).toLocaleString()
          ) : (
            <span className="text-gray-400 italic">N/A</span>
          ),
      },
];


const acceptedColumns = [
  { title: t("id"), dataIndex: "id", key: "id" },
  {
    title: t("passport_number"),
    dataIndex: "passport_number",
    render: (val: string) => val || "N/A",
  },
  {
    title: t("employee_id"),
    dataIndex: "employee_id",
    render: (val: string) => val || "N/A",
  },
  {
    title: t("status"),
    dataIndex: "status",
    render: (status: string) => (
      <span className="px-2 py-1 rounded bg-green-100 text-green-600">
        {status}
      </span>
    ),
  },
  {
  title: t("payment_cv"),
  key: "payment",
  render: (_: any, record: any) => {
    if (!record.is_paid) {
      return (
        <Button
          type="primary"
          loading={payingId === record.id}
          onClick={() => handlePay(record.id, record.cv_id)}
        >
          Pay ${record.price ?? ""}
        </Button>
      );
    }

    return (
      <div className="flex gap-2">
        <Button
          type="default"
          onClick={() => {
            generateCvDataDownload
              .mutateAsync({
                requestBody: {
                  user_id: record.recruitment_id, // ✅ use correct ID
                },
              })
              .then((r: any) => {
                const printWindow = window.open(
                  "",
                  "_blank",
                  "toolbar=no,status=no,menubar=no,scrollbars=yes,resizable=yes,width=1920,height=1080"
                );

                if (printWindow) {
                  printWindow.document.write(r.data);
                  printWindow.document.close();
                  printWindow.print();
                }
              });
          }}
        >
          {t("Download_CV")}
        </Button>
      </div>
    );
  },
},


/*
  {
  title: "Payment / CV",
  key: "payment",
  render: (_: any, record: any) => {
    if (!record.is_paid) {
      return (
        <Button
          type="primary"
          loading={payingId === record.id}
          onClick={() => handlePay(record.id, record.cv_id)}
        >
          Pay ${record.price ?? ""}
        </Button>
      );
    }

    return (
      <div className="flex gap-2">
        <span className="text-green-600 font-medium">Paid</span>
        <Button
          onClick={() => {
            window.open(
              `${import.meta.env.VITE_BASE_URL}/api/v1/cv/download/${record.cv_id}`, // ✅ FIX HERE
              "_blank"
            );
          }}
        >
          Download CV
        </Button>
      </div>
    );
  },
},
*/

/*

  {
    title: "Payment / CV",
    key: "payment",
    render: (_: any, record: any) => {
      // 🔴 NOT PAID → SHOW PAY BUTTON
      if (!record.is_paid) {
        return (
          <Button
            type="primary"
            loading={payingId === record.id}
            onClick={() => handlePay(record.id, record.cv_id)}
          >
            Pay
          </Button>
        );
      }

      // 🟢 PAID → SHOW DOWNLOAD CV
      return (
        <Button
          type="default"
          onClick={() => {
            window.open(
              `${import.meta.env.VITE_BASE_URL}/api/v1/cv/download/${record.id}`,
              "_blank"
            );
          }}
        >
          Download CV
        </Button>
      );
    },
  },
*/
  {
    title: t("Created At"),
    dataIndex: "created_at",
    render: (date: string) =>
      date ? new Date(date).toLocaleString() : "N/A",
  },
];

const secondacceptedColumns = [
  { title: t("id"), dataIndex: "id", key: "id" },
  {
    title: t("passport_number"),
    dataIndex: "passport_number",
    render: (val: string) => val || "N/A",
  },
  {
    title: t("employee_id"),
    dataIndex: "employee_id",
    render: (val: string) => val || "N/A",
  },
  {
    title: t("status"),
    dataIndex: "status",
    render: (status: string) => (
      <span className="px-2 py-1 rounded bg-green-100 text-green-600">
        {status}
      </span>
    ),
  },
  {
  title: t("payment_cv"),
  key: "payment",
  render: (_: any, record: any) => {
    if (!record.is_paid) {
      return (
        <Button
          type="primary"
          loading={payingId === record.id}
          onClick={() => handlePay(record.id, record.cv_id)}
        >
          Pay ${record.price ?? ""}
        </Button>
      );
    }

    return (
      <div className="flex gap-2">
        <Button
          type="default"
          onClick={() => {
            generateCvDataDownload
              .mutateAsync({
                requestBody: {
                  user_id: record.recruitment_id, // ✅ use correct ID
                },
              })
              .then((r: any) => {
                const printWindow = window.open(
                  "",
                  "_blank",
                  "toolbar=no,status=no,menubar=no,scrollbars=yes,resizable=yes,width=1920,height=1080"
                );

                if (printWindow) {
                  printWindow.document.write(r.data);
                  printWindow.document.close();
                  printWindow.print();
                }
              });
          }}
        >
          {t("Download_CV")}
        </Button>
      </div>
    );
  },
},


/*
  {
  title: "Payment / CV",
  key: "payment",
  render: (_: any, record: any) => {
    if (!record.is_paid) {
      return (
        <Button
          type="primary"
          loading={payingId === record.id}
          onClick={() => handlePay(record.id, record.cv_id)}
        >
          Pay ${record.price ?? ""}
        </Button>
      );
    }

    return (
      <div className="flex gap-2">
        <span className="text-green-600 font-medium">Paid</span>
        <Button
          onClick={() => {
            window.open(
              `${import.meta.env.VITE_BASE_URL}/api/v1/cv/download/${record.cv_id}`, // ✅ FIX HERE
              "_blank"
            );
          }}
        >
          Download CV
        </Button>
      </div>
    );
  },
},
*/

/*

  {
    title: "Payment / CV",
    key: "payment",
    render: (_: any, record: any) => {
      // 🔴 NOT PAID → SHOW PAY BUTTON
      if (!record.is_paid) {
        return (
          <Button
            type="primary"
            loading={payingId === record.id}
            onClick={() => handlePay(record.id, record.cv_id)}
          >
            Pay
          </Button>
        );
      }

      // 🟢 PAID → SHOW DOWNLOAD CV
      return (
        <Button
          type="default"
          onClick={() => {
            window.open(
              `${import.meta.env.VITE_BASE_URL}/api/v1/cv/download/${record.id}`,
              "_blank"
            );
          }}
        >
          Download CV
        </Button>
      );
    },
  },
*/
  {
    title: t("Created At"),
    dataIndex: "created_at",
    render: (date: string) =>
      date ? new Date(date).toLocaleString() : "N/A",
  },
];


  if (loading) return <Spin />;

  return (
    <div className="p-6">
      <h2 className="text-lg font-semibold mb-4">
        {t("recruiter_residence")}
      </h2>
      <Modal
        title="Approve Reservation"
        open={isModalOpen}
        onOk={() => {
           if (selectedRecord) {
            handleApproveSponsor(recruiter_id, withPassport, cv_id); // ✅ use recruiter_id from localStorage
          }
          setIsModalOpen(false);
        }}
        onCancel={() => setIsModalOpen(false)}
      >
        <Select
          defaultValue={false}
          style={{ width: "100%" }}
          onChange={(value) => setWithPassport(value)}
          options={[
            { label: t("without_passport"), value: false },
            { label: t("with_passport"), value: true },
          ]}
        />
      </Modal>
      
      {showPaymentModal && checkoutId && (
  <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
    <div className="bg-white p-6 rounded-lg w-full max-w-md relative">
      <button
        className="absolute top-2 right-2"
        onClick={() => setShowPaymentModal(false)}
      >
        ✕
      </button>

      <h2 className="text-lg font-semibold mb-4 text-center">
      {t("Complete Payment")} 
      </h2>

            <form
      
        action="https://marrir.com/recruitment-transfer/pay-history"
        className="paymentWidgets"
        data-brands="VISA MASTER AMEX"
      ></form>

     
    </div>
  </div>
)}


{showSecondPaymentModal && SecondcheckoutId && (
  <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
    <div className="bg-white p-6 rounded-lg w-full max-w-md relative">
      <button
        className="absolute top-2 right-2"
        onClick={() => setShowSecondPaymentModal(false)}
      >
        ✕
      </button>

      <h2 className="text-lg font-semibold mb-4 text-center">
      {t("Complete Payment")} 
      </h2>

            <form
      
        action="https://marrir.com/recruitment-transfer/pay-history/second"
        className="paymentWidgets"
        data-brands="VISA MASTER AMEX"
      ></form>

     
    </div>
  </div>
)}

      <Table
        rowKey="id"
        columns={columns}
        dataSource={buyerRequests}
        pagination={{ pageSize: 5 }}
      />

      <div className="mt-10">
  <h2 className="text-lg font-semibold mb-4">
    {t("Accepted Reserves")}
  </h2>

  <Table
    rowKey="id"
    columns={acceptedColumns}
    dataSource={acceptedReserves}
    loading={acceptedLoading}
    pagination={{ pageSize: 5 }}
  />
</div>



  <div className="mt-10">
  <h2 className="text-lg font-semibold mb-4">
    {t("Sponsor Requests")}
  </h2>

  <Table
    rowKey="id"
    columns={secondacceptedColumns}
    dataSource={Reserves}
    loading={acceptedLoading}
    pagination={{ pageSize: 5 }}
  />
</div>

    </div>
  );
};

export default RecruitmentReserveDash;
