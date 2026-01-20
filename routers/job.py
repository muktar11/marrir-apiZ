import {
  Button,
  Checkbox,
  DatePicker,
  Dropdown,
  Input,
  Menu,
  MenuProps,
  Modal,
  Select,
  Spin,
  Table,
  message,
} from "antd";
import { GoTriangleUp } from "react-icons/go";
import { tw } from "typewind";
import { useStores } from "../../../hooks/useStores";
import {
  ApplyJobSingleReadSchema,
  JobReadSchema,
  OfferTypeSchema,
  UserCVFilterSchema,
  UserReadSchema_Output,
  UserRoleSchema,
} from "../../../api/requests";
import { useEffect, useState } from "react";
import {
  useCvServiceGenerateCvReportApiV1CvGenerateReportPost,
  useCvServiceGenerateSaudiReportApiV1CvGenerateSaudiPost,
  useJobServiceApplyForJobApiV1JobApplyPost,
  useJobServiceCloseJobPostApiV1JobCloseDelete,
  useJobServiceReadJobPostApiV1JobSinglePost,
  useOfferServiceSendOfferApiV1OfferPost,
  useUserServiceReadManagedUserCvsApiV1UserEmployeesCvPost,
  useUserServiceReadManagedUsersApiV1UserEmployeesPost,
} from "../../../api/queries";
import { useNavigate, useParams } from "react-router-dom";
import { snakeToCapitalized } from "../../../Utils/snakeToCapitalized";
import moment from "moment";
import { ColumnsType } from "antd/es/table";
import { EllipsisOutlined } from "@ant-design/icons";
import { Dayjs } from "dayjs";
import UserFilter from "../../../components/common/UserFilter";
import { CustomPagination } from "../../../types/Pagination";
import { RangePickerProps } from "antd/es/date-picker/generatePicker/interface";
import { useTranslation } from "react-i18next";
import axios from "axios";
import { toast, ToastContainer } from "react-toastify";
import StatusCard from "../../../components/common/StatusCard";

const { Search } = Input;
const { RangePicker } = DatePicker;
const { Option } = Select;

interface DataType {
  Photo?: any;
  Name: string;
  PassportNumber: string;
  Email?: string | null;
  PhoneNumber?: string;
  Status?: string;
  User: UserReadSchema_Output;
}

interface ApplicationDataType {
  Photo?: any;
  Name?: string | null;
  Status?: string;
  User: UserReadSchema_Output;
  JobApplication: ApplyJobSingleReadSchema;
}
/*
const NewJobDetails = () => {
  const { t } = useTranslation();
  const { id } = useParams();
  const { userStore } = useStores();
  const router = useNavigate();
  const acceptJobApplication = useOfferServiceSendOfferApiV1OfferPost();
  const closeJobPost = useJobServiceCloseJobPostApiV1JobCloseDelete();
  const applyForJob = useJobServiceApplyForJobApiV1JobApplyPost();

  const navigate = useNavigate();
  const [job, setJob] = useState<JobReadSchema | null>(null);
  const [hasApplied, setHasApplied] = useState<Boolean>(false);
  const role = userStore.user?.role;
  const columns: ColumnsType<DataType> = [
    {
      title: "",
      dataIndex: "Photo",
      width: "5%",
    },
    {
      title: t("job_detail_name"),
      dataIndex: "Name",
      width: "20%",
    },
    {
      title: t("job_detail_cv_view"),
      dataIndex: "ViewCV",
      width: "20%",
    },
    {
      title: t("job_detail_passport_number"),
      dataIndex: "PassportNumber",
      width: "15%",
    },
    
    {
      title: t("job_detail_email"),
      dataIndex: "Email",
      width: "20%",
    },
    {
      title: t("job_detail_phone_number"),
      dataIndex: "PhoneNumber",
      width: "15%",
    },
  
    {
      title: t("job_detail_status"),
      dataIndex: "Status",
      width: "10%",
      key: "Status",
      render: (status: string) => (
        <span
          className={`inline-block px-3 py-1 text-sm rounded-full border 
            ${
              status === "approved"
                ? "border-green-500 text-green-600 bg-green-50"
                : "border-gray-400 text-gray-600 bg-gray-100"
            }`}
        >
          {status.charAt(0).toUpperCase() + status.slice(1)}
        </span>
      ),
    },
  ];

  const generateCvData =
    useCvServiceGenerateCvReportApiV1CvGenerateReportPost();
  const saudiReport = useCvServiceGenerateSaudiReportApiV1CvGenerateSaudiPost();

  const items: MenuProps["items"] = [];

  const menuProps = {
    items,
  };

  const applicationColumns = [
    {
      title: "",
      dataIndex: "select",
      width: "5%",
      render: (_, record) => (
        <Checkbox
          onChange={(e) => handleCheckboxChange(record.id, e.target.checked)}
          checked={selectedJobIds.includes(record.id)}
          disabled={record.status !== "pending"} // Enable only for pending applications
        />
      ),
    },
    {
      title: t("Name"),
      dataIndex: "name",
      width: "20%",
      render: (_, record) =>
        record?.user?.cv.english_full_name
          ? `${record.user.cv.english_full_name}`
          : "N/A",
    },
    {
      title: "CV",
      key: "select",
      width: "20%",
      render: (_: any, record: any) => (
        <button
          className="px-4 py-2 mt-4 bg-blue-600 text-white rounded-lg text-lg font-semibold transition-all duration-300 hover:bg-blue-700"
          onClick={() => handleNavigate(record.user_id)}
        >
          {t("View")}
        </button>
      ),
    },
    // {
    //   title: "Status",
    //   dataIndex: "status",
    //   width: "10%",
    //   render: (_, record) => record?.status || "N/A",
    // },
    // ... existing code ...
    {
      title: t("reserve_history_expanded_status"),
      key: "status",
      render: (text: any, reserve: any) => (
        <div className="flex items-center gap-2">
          <StatusCard status={reserve.status} />
          {reserve.status === "accepted" && (
            <Dropdown.Button
              menu={menuProps}
              onClick={() => {
                generateCvData
                  .mutateAsync({
                    requestBody: {
                      user_id: reserve?.user?.cv?.user_id,
                    },
                  })
                  .then((r: any) => {
                    let printWindow = window.open(
                      "",
                      "_blank",
                      "toolbar=no,status=no,menubar=no,scrollbars=no,resizable=no,left=10000, top=10000, width=1920, height=1080, visible=none"
                    );
                    if (printWindow) {
                      printWindow.document.write(r.data);
                      printWindow.document.close();
                      printWindow.print();
                    }
                  });
              }}
            >
              {t("download_cv")}
            </Dropdown.Button>
          )}
        </div>
      ),
      width: "15%",
    },

  ];

  const [selectedApplications, setSelectedApplications] = useState<number[]>(
    []
  );
  const [selectedJobIds, setSelectedJobIds] = useState<number[]>([]);

  
  const handleCheckboxChange = (jobId: number, checked: boolean) => {
    setSelectedJobIds((prevSelected) =>
      checked
        ? [...prevSelected, jobId]
        : prevSelected.filter((id) => id !== jobId)
    );
  };

  const [paymentData, setPaymentData] = useState(null);

  useEffect(() => {
    const fetchApplications = async () => {
      try {
        const userToken = localStorage.getItem("accessToken");
        if (!userToken) {
          console.error("No access token found.");
          return;
        }
        const JobId = localStorage.getItem("jobId");
        const response = await axios.get(
          `${
            import.meta.env.VITE_BASE_URL
          }/api/v1/job/my-applications/${JobId}`,
          {
            headers: {
              Authorization: `Bearer ${userToken}`, 
              "Content-Type": "application/json",
            },
          }
        );
        const formattedData = response.data.map((app) => ({
          ...app,
          key: app.id, 
        }));
        setTableApplicationDataSources(formattedData);
      } catch (error) {
        console.error("Error fetching applications:", error);
      }
    };
    fetchApplications();
  }, []); 

  const handlePayment = async (batch: any, setPaymentData: any) => {
    try {
      
      const token = localStorage.getItem("accessToken");
      if (!token) {
        message.error("User not authenticated");
        return;
      }
      if (selectedJobIds.length === 0) {
        message.warning("Please select at least one job application.");
        return;
      }
      const JobId = localStorage.getItem("jobId");
      const requestData = {
        job_application_ids: selectedJobIds,
        job_id: parseInt(JobId, 10),
      };

      
      const usetoken = localStorage.getItem("accessToken");
      const response = await axios.post(
        `${
          import.meta.env.VITE_BASE_URL
        }/api/v1/job/my-applications/payment/info`,
        requestData, 
        {
          headers: {
            Authorization: `Bearer ${usetoken}`,
            "Content-Type": "application/json",
          },
        }
      );

      if (!response.data) {
        throw new Error("No payment data received.");
      }

      setPaymentData(response.data); 
      Modal.confirm({
        title: "Reserve Payment Details",
        content: (
          <div>
            <p>Number of Profiles: {response.data.profile}</p>
            <p>Price per Profile: ${response.data.price.toFixed(2)}</p>
            <p>Total Amount: ${response.data.total_amount.toFixed(2)}</p>
          </div>
        ),
        onOk: async () => {
          try {
            
            const JobId = localStorage.getItem("jobId");
            const usetoken = localStorage.getItem("accessToken");
            const jobIdNumber = JobId ? parseInt(JobId, 10) : null;
            if (!jobIdNumber) {
              message.error("Invalid Job ID.");
              return;
            }

            if (!usetoken) {
              message.error("User not authenticated.");
              return;
            }

            if (selectedJobIds.length === 0) {
              message.warning("Please select at least one job application.");
              return;
            }

            
            const requestedData = {
              job_application_ids: selectedJobIds, 
              status: "accepted",
            };

            const telrResponse = await axios.patch(
              `${
                import.meta.env.VITE_BASE_URL
              }/api/v1/job/my-applications/${JobId}/status`,
              requestedData,
              {
                headers: {
                  Authorization: `Bearer ${usetoken}`,
                  "Content-Type": "application/json",
                },
              }
            );

            if (telrResponse.data?.order?.url) {
              localStorage.setItem("ref", telrResponse.data.order.ref);
              window.location.href = telrResponse.data.order.url;
            } else {
              throw new Error("Invalid payment response");
            }
          } catch (error: any) {
            
            message.error(
              error?.response?.data?.detail ||
                "Payment failed. Please try again."
            );
          }
        },
      });
    } catch (error: any) {
      console.error("Payment error:", error);
      message.error(
        error?.response?.data?.detail || "An error occurred. Please try again."
      );
    }
  };

  const handlePaymentCallback = async () => {
    try {
      
      const token = localStorage.getItem("accessToken");
      if (!token) {
        message.error("User not authenticated");
        return;
      }
      
      const ref = localStorage.getItem("ref");
      if (!ref) {
        console.warn("No reference found in localStorage.");
        return;
      }
      const requestData = {
        ref: ref, 
      };
      
      const response = await axios.post(
        `${
          import.meta.env.VITE_BASE_URL
        }/api/v1/job/my-applications/status/callback`,
        requestData,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        }
      );
      if (!response.data) {
        throw new Error("No payment data received.");
      }
      
      
      if (response?.status && response.status === 200) {
        message.success("Payment successful!");
        localStorage.removeItem("ref");
      }
    } catch (error) {
    
      message.error("Failed to verify payment status.");
    }
  };

  
  useEffect(() => {
    const ref = localStorage.getItem("ref");
    if (ref) {
      handlePaymentCallback();
    }
  }, []);

  const [searchTerm, setSearchTerm] = useState<string>("");
  const [dateRange, setDateRange] = useState<[Dayjs | null, Dayjs | null]>([
    null,
    null,
  ]);
  const [pageSize, setPageSize] = useState(10);
  const [pagination, setPagination] = useState<CustomPagination>({
    limit: pageSize,
    skip: 0,
  });
  const [tableDataSource, setTableDataSource] = useState<DataType[]>([]);
  const [tableApplicationDataSource, setTableApplicationDataSource] = useState<
    ApplicationDataType[]
  >([]);

  const [tableApplicationDataSources, setTableApplicationDataSources] =
    useState<ApplicationDataType[]>([]);
  const [paginatedUsers, setPaginatedUsers] = useState<any[]>([]);
  const [filter, setFilter] = useState<UserCVFilterSchema>({});
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);

  const onSearch = (value: string) => {
    setSearchTerm(value);
    
  };

  const onSelectChange = (selectedRowKeys: any) => {
    setSelectedRowKeys(selectedRowKeys);
  };

  const rowSelection = {
    selectedRowKeys,
    onChange: onSelectChange,
    columnWidth: "3%",
    getCheckboxProps: (record: any) => ({
      disabled: record.hasApplied,
    }),
  };
  const onDateRangeChange: RangePickerProps<Dayjs>["onChange"] = (dates) => {
    setDateRange(dates as [Dayjs | null, Dayjs | null]);
  };

  const handlePageSizeChange = (value: number) => {
    setPagination({ ...pagination, limit: value });
    setPageSize(value);
  };

  const handlePaginationChange = (page: number, pageSize?: number) => {
    if (pageSize) {
      setPagination({ limit: pageSize, skip: (page - 1) * pageSize });
    }
  };

  const {
    data: jobData,
    isError: jobIsError,
    isLoading: jobIsLoading,
    mutateAsync,
  } = useJobServiceReadJobPostApiV1JobSinglePost({
    onSuccess: (data) => {
      if (data) setJob(data.data);
      data.data?.job_applications &&
        setHasApplied(
          data.data?.job_applications?.some(
            (application) => application.user_id === userStore.user?.id
          )
        );
    },
    onError: (error, variables, context) => {},
  });

  const {
    data: employeesData,
    isError: employeeIsError,
    isLoading: employeesIsLoading,
    mutateAsync: employeesMutateAsync,
  } = useUserServiceReadManagedUserCvsApiV1UserEmployeesCvPost({
    onSuccess: (data) => {
      if (data) {
        setPaginatedUsers(data.data);
      }
    },
    onError: (error, variables, context) => {},
  });

  const acceptApplication = async (userId: string, detail: string) => {
    const response = await acceptJobApplication
      .mutateAsync({
        requestBody: {
          job_id: parseInt(id!),
          receiver_id: userId,
          detail: detail,
        },
      })
      .then((data) => {
        message.success("Accepted Job Application");
        window.location.reload();
      })
      .catch((error) => {
        message.error(
          error.body?.message || "Failed to accept job application"
        );
      });
  };

  const jobApply = async (userIds: string[]) => {
    const response = await applyForJob
      .mutateAsync({
        requestBody: {
          job_id: job?.id!,
          user_id: userIds,
        },
      })
      .then((data) => {
        message.success("Applied for job successfully!");
        setTimeout(() => {
          window.location.reload();
        }, 1500);
      })
      .catch((error) => {
        message.error(error.body.message || "Job application failed");
      });
  };

  const closeJob = async () => {
    await closeJobPost
      .mutateAsync({
        requestBody: {
          id: parseInt(id!),
        },
      })
      .then((data: any) => {
        message.success("Job post closed successfully!");
        router(-1);
      })
      .catch((error: any) => {
        message.success("Unable to close job post successfully!");
      });
  };

  useEffect(() => {
    mutateAsync({
      requestBody: {
        id: parseInt(id!),
      },
    });
  }, []);

  useEffect(() => {
    const fetchUsers = async () => {
      const formattedStartDate = dateRange[0]?.format("YYYY-MM-DD");
      const formattedEndDate = dateRange[1]?.format("YYYY-MM-DD");

      const response = await employeesMutateAsync({
        limit: pagination.limit,
        skip: pagination.skip,
        search: searchTerm,
        startDate: formattedStartDate,
        endDate: formattedEndDate,
        managerId: userStore.user?.id!,
        requestBody: filter,
      });
    };

    {
      userStore.user?.role !== UserRoleSchema.EMPLOYEE && fetchUsers();
    }
  }, [searchTerm, dateRange, pagination, filter]);

  const handleNavigate = (user_id: string) => {
    navigate(`/${role}/view/employees/${user_id}`);
  };

  const handleCVNavigate = (user_id: string) => {
    navigate(`/${role}/employees/${user_id}`);
  };

  useEffect(() => {
    if (paginatedUsers) {
      const tableData: DataType[] = paginatedUsers.map((employee) => ({
        hasApplied: jobData?.data?.job_applications?.some((application) => {
          return application.user_id === employee.id;
        }),
        Photo:
          employee.cv && employee.cv.head_photo ? (
            <div className="w-10 h-10 rounded-full overflow-hidden">
              <img
                className="w-full h-full object-cover"
                src={`${import.meta.env["VITE_BASE_URL"]}/static/${
                  employee.cv.head_photo
                }`}
                alt="Profile Picture"
              />
            </div>
          ) : (
            <div className="w-10 h-10 rounded-full bg-gray-400"></div>
          ),
        Name: employee.cv
          ? employee.cv?.english_full_name
          : employee.first_name || employee.last_name
          ? employee.first_name + " " + employee.last_name
          : "N/A",
        PassportNumber: employee.cv ? employee.cv.passport_number : "N/A",
        Email:
          employee.cv && employee.cv?.email
            ? employee.cv?.email
            : employee.email
            ? employee.email
            : "N/A",
        PhoneNumber: employee.phone_number?.split(":")[1] || "N/A",
        Status: snakeToCapitalized(employee.status || ""),
        ViewCV: employee.cv ? (
          <button
            className="px-4 py-2 mt-4 bg-blue-600 text-white rounded-lg text-lg font-semibold transition-all duration-300 hover:bg-blue-700"
            onClick={() => handleCVNavigate(employee.cv.user_id)}
          >
            View
          </button>
        ) : (
          <span className="text-gray-500">No CV</span>
        ),

        DownloadCV:
          employee.cv && employee.cv.cv_file ? (
            <a
              href={`${import.meta.env["VITE_BASE_URL"]}/static/${
                employee.cv.cv_file
              }`}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1 text-white bg-blue-500 rounded-md hover:bg-blue-600"
            >
              Download CV
            </a>
          ) : (
            <span className="text-gray-500">No CV</span>
          ),
        User: employee,
      }));

      setTableDataSource(tableData);
    }
  }, [paginatedUsers]);

  useEffect(() => {
    if (jobData?.data?.job_applications) {
      const applications = jobData?.data?.job_applications;
      const tableData: ApplicationDataType[] = applications.map(
        (application) => ({
          Photo:
            application.user?.cv && application.user.cv.head_photo ? (
              <div className="w-10 h-10 rounded-full overflow-hidden">
                <img
                  className="w-full h-full object-cover"
                  src={`${import.meta.env["VITE_BASE_URL"]}/static/${
                    application.user.cv.head_photo
                  }`}
                  alt="Profile Picture"
                />
              </div>
            ) : (
              <div className="w-10 h-10 rounded-full bg-gray-400"></div>
            ),
          Name: application.user?.cv
            ? application.user.cv?.english_full_name
            : application.user?.first_name || application.user?.last_name
            ? application.user?.first_name + " " + application.user?.last_name
            : "N/A",
          Status: snakeToCapitalized(application.status || ""),
          User: application.user!,
          JobApplication: application,
        })
      );

      setTableApplicationDataSource(tableData);
    }
  }, [jobData?.data?.job_applications]);

  return (
    <div className={tw.p_5.h_screen}>
      {jobIsLoading ? (
        <Spin />
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
            <div>
              <div className={tw.flex.flex_col.space_x_1.mb_8}>
                <span>
                  {jobData?.data?.deleted_at ? (
                    <div className="w-fit bg-red-200 text-red-500 p-1 px-4 rounded-md">
                      {t("job_detail_closed")}
                    </div>
                  ) : (
                    <div className="w-fit bg-green-200 text-green-500 p-1 px-4">
                      {t("job_detail_active")}
                    </div>
                  )}
                </span>
                <span className={tw.text_black}>
                  {t("job_detail_posted_on")}:
                  {moment(jobData?.data?.created_at).format("MMM DD, YYYY")}
                </span>
              </div>
              <div
                className={tw.flex.flex_col.space_x_0.space_y_4.justify_start.items_start.mb_10.md(
                  tw.flex.flex_row.space_x_4.space_y_0
                )}
              >
                <div
                  className={
                    tw.w_["260px"].h_["135px"].bg_white.rounded_md.py_6.px_8
                      .shadow.flex.flex_col.space_y_1.items_start.justify_start
                  }
                >
                  <span className={tw.text_gray_500.text_base}>
                    {t("job_detail_number_of_applications")}
                  </span>
                  <span className={tw.text_2xl.font_bold}>
                    {jobData?.data?.job_applications?.length}
                  </span>
                  <div
                    className={tw.flex.flex_row.space_x_1.justify_end.items_end}
                  >
                    <span className={tw.text_sm}>Count </span>
                    <GoTriangleUp className={tw.text_green_500} size={20} />
                    <span className={tw.text_green_500}>0%</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="mb-10">
              <h2 className="text-2xl font-semibold text-black mb-6">
                {t("job_detail_info")}
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-white shadow rounded-xl p-6">
                <div>
                  <p className="text-sm text-black mb-1">
                    {t("job_description")}
                  </p>
                  <p className="text-base font-medium text-black">
                    {jobData?.data?.description || "-"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-black mb-1">{t("job_location")}</p>
                  <p className="text-base font-medium text-black">
                    {jobData?.data?.location || "-"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-black mb-1">
                    {t("job_occupation")}
                  </p>
                  <p className="text-base font-medium text-black capitalize">
                    {jobData?.data?.occupation?.replaceAll("_", " ") || "-"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-black mb-1">
                    {t("job_education")}
                  </p>
                  <p className="text-base font-medium text-black capitalize">
                    {jobData?.data?.education_status?.replaceAll("_", " ") ||
                      "-"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-black mb-1">{t("job_type")}</p>
                  <p className="text-base font-medium text-black capitalize">
                    {jobData?.data?.type?.replaceAll("_", " ") || "-"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-black mb-1">
                    {t("job_vacancies")}
                  </p>
                  <p className="text-base font-medium text-black">
                    {jobData?.data?.amount || "-"}
                  </p>
                </div>
              </div>
            </div>
          </div>

          

          {job?.posted_by === userStore.user?.id ? (
            <div className={tw.flex.flex_col.space_x_1.mb_8}>
              <span className={tw.text_2xl.font_semibold.text_primaryBlue}>
                {t("job_detail_applications")}
              </span>
              <div style={{ marginTop: 16, textAlign: "right" }}>
                <Button
                  type="primary"
                  disabled={selectedJobIds.length === 0} 
                  onClick={() => handlePayment(selectedJobIds, setPaymentData)} 
                >
                  Accept
                </Button>
              </div>

              <Table
                columns={applicationColumns}
                dataSource={tableApplicationDataSources}
                scroll={{ x: true }}
              />

              {!jobData?.data?.deleted_at && (
                <div className={tw.flex.w_full.justify_end.mt_8.mb_8.gap_x_2}>
                  <Button
                    className={tw.border_0.bg_primaryBlue.w_[
                      "1/4"
                    ].h_10.rounded_sm.text_white.justify_end.items_end.mt_6.md(
                      tw.mt_0
                    )}
                    onClick={() => router(`/sponsor/jobs/${id}/edit`)}
                  >
                    {t("job_detail_edit")}
                  </Button>
                  <Button
                    className={tw.border_0.bg_red_400.w_[
                      "1/4"
                    ].h_10.rounded_sm.text_white.justify_end.items_end.mt_6.md(
                      tw.mt_0
                    )}
                    onClick={closeJob}
                  >
                    {t("job_detail_close_job_post")}
                  </Button>
                </div>
              )}
            </div>
          ) : userStore.user?.role !== UserRoleSchema.EMPLOYEE &&
            userStore.user?.role !== UserRoleSchema.ADMIN ? (
            <>
              <div
                className={tw.flex_col.space_y_4.space_x_0.justify_between.mb_4.lg(
                  tw.flex.flex_row.space_y_0.space_x_4.mb_4
                )}
              >
                <div className={tw.flex.flex_col.space_y_3.mb_3}>
                  <span className={tw.text_black.font_medium.text_lg}>
                    {t("job_detail_employee")}
                  </span>
                </div>
                <div className={tw.flex.space_x_2.items_center}>
                  <Search
                    placeholder={t("job_detail_passport_number")}
                    allowClear
                    style={{ width: 300 }}
                    onSearch={onSearch}
                  />

                  <UserFilter filter={filter} setFilter={setFilter} />
                  <Button
                    className="px-4 py-2 mt-4 bg-blue-600 text-white rounded-lg text-lg font-semibold transition-all duration-300 hover:bg-blue-700"
                    size="large"
                    onClick={async () => await jobApply(selectedRowKeys)}
                  >{`${t("job_detail_apply")} (${
                    selectedRowKeys.length
                  })`}</Button>
                </div>
              </div>
              {employeesIsLoading ? (
                <Spin />
              ) : (
                <Table
                  rowSelection={rowSelection}
                  columns={columns}
                  dataSource={tableDataSource}
                  scroll={{ x: true }}
                  pagination={{
                    total: employeesData?.count || 0,
                    pageSize: pagination.limit,
                    current: pagination.skip / pagination.limit + 1,
                    onChange: handlePaginationChange,
                  }}
                  rowKey={(record) => record.User.id!}
                />
              )}
              <div className={tw.flex.justify_center}>
                <Select
                  defaultValue={pageSize}
                  style={{ width: 120 }}
                  onChange={handlePageSizeChange}
                >
                  <Option value={10}>10</Option>
                  <Option value={20}>20</Option>
                  <Option value={50}>50</Option>
                  <Option value={100}>100</Option>
                </Select>
              </div>
            </>
          ) : (
            userStore.user.role !== UserRoleSchema.ADMIN && (
              <>
                <Button
                  disabled={hasApplied ? true : false}
                  className="bg-[#1677ff] text-white"
                  size="large"
                  onClick={async () => await jobApply([userStore.user?.id!])}
                >
                  {applyForJob.isLoading ? (
                    <Spin />
                  ) : hasApplied ? (
                    t("job_detail_applied")
                  ) : (
                    t("job_detail_apply")
                  )}
                </Button>
              </>
            )
          )}
        </>
      )}
    </div>
  );
};

export default NewJobDetails;
*/





import { extractToken } from "../../../Utils/extractToken";
const NewJobDetails = () => {
  const { t } = useTranslation();
  const { id } = useParams();
  const { userStore } = useStores();
  const router = useNavigate();
  const acceptJobApplication = useOfferServiceSendOfferApiV1OfferPost();
  const closeJobPost = useJobServiceCloseJobPostApiV1JobCloseDelete();
  const applyForJob = useJobServiceApplyForJobApiV1JobApplyPost();

  const navigate = useNavigate();
  const [job, setJob] = useState<JobReadSchema | null>(null);
  const [hasApplied, setHasApplied] = useState<Boolean>(false);
  
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [checkoutId, setCheckoutId] = useState<string | null>(null);
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);
  const userData = extractToken(localStorage.getItem("accessToken")!);
  
  const role = userStore.user?.role;
  const columns: ColumnsType<DataType> = [
    {
      title: "",
      dataIndex: "Photo",
      width: "5%",
    },
    {
      title: t("job_detail_name"),
      dataIndex: "Name",
      width: "20%",
    },
    {
      title: t("job_detail_cv_view"),
      dataIndex: "ViewCV",
      width: "20%",
    },
    {
      title: t("job_detail_passport_number"),
      dataIndex: "PassportNumber",
      width: "15%",
    },
   
    {
      title: t("job_detail_email"),
      dataIndex: "Email",
      width: "20%",
    },
    {
      title: t("job_detail_phone_number"),
      dataIndex: "PhoneNumber",
      width: "15%",
    },
   
    {
      title: t("job_detail_status"),
      dataIndex: "Status",
      width: "10%",
      key: "Status",
      render: (status: string) => (
        <span
          className={`inline-block px-3 py-1 text-sm rounded-full border 
            ${
              status === "approved"
                ? "border-green-500 text-green-600 bg-green-50"
                : "border-gray-400 text-gray-600 bg-gray-100"
            }`}
        >
          {status.charAt(0).toUpperCase() + status.slice(1)}
        </span>
      ),
    },
  ];

  const generateCvData =
    useCvServiceGenerateCvReportApiV1CvGenerateReportPost();
  const saudiReport = useCvServiceGenerateSaudiReportApiV1CvGenerateSaudiPost();

  const items: MenuProps["items"] = [];

  const menuProps = {
    items,
  };

  const applicationColumns = [
    {
      title: "",
      dataIndex: "select",
      width: "5%",
      render: (_, record) => (
        <Checkbox
          onChange={(e) => handleCheckboxChange(record.id, e.target.checked)}
          checked={selectedJobIds.includes(record.id)}
          disabled={record.status !== "pending"} // Enable only for pending applications
        />
      ),
    },
    {
      title: t("Name"),
      dataIndex: "name",
      width: "20%",
      render: (_, record) =>
        record?.user?.cv.english_full_name
          ? `${record.user.cv.english_full_name}`
          : "N/A",
    },
    {
      title: "CV",
      key: "select",
      width: "20%",
      render: (_: any, record: any) => (
        <button
          className="px-4 py-2 mt-4 bg-blue-600 text-white rounded-lg text-lg font-semibold transition-all duration-300 hover:bg-blue-700"
          onClick={() => handleNavigate(record.user_id)}
        >
          {t("View")}
        </button>
      ),
    },
    
    {
      title: t("reserve_history_expanded_status"),
      key: "status",
      render: (text: any, reserve: any) => (
        <div className="flex items-center gap-2">
          <StatusCard status={reserve.status} />
          {reserve.status === "accepted" && (
            <Dropdown.Button
              menu={menuProps}
              onClick={() => {
                generateCvData
                  .mutateAsync({
                    requestBody: {
                      user_id: reserve?.user?.cv?.user_id,
                    },
                  })
                  .then((r: any) => {
                    let printWindow = window.open(
                      "",
                      "_blank",
                      "toolbar=no,status=no,menubar=no,scrollbars=no,resizable=no,left=10000, top=10000, width=1920, height=1080, visible=none"
                    );
                    if (printWindow) {
                      printWindow.document.write(r.data);
                      printWindow.document.close();
                      printWindow.print();
                    }
                  });
              }}
            >
              {t("download_cv")}
            </Dropdown.Button>
          )}
        </div>
      ),
      width: "15%",
    },
    // ... existing code ...
   
  ];

  const [selectedApplications, setSelectedApplications] = useState<number[]>(
    []
  );
  const [selectedJobIds, setSelectedJobIds] = useState<number[]>([]);

  // Handle checkbox selection
  const handleCheckboxChange = (jobId: number, checked: boolean) => {
    setSelectedJobIds((prevSelected) =>
      checked
        ? [...prevSelected, jobId]
        : prevSelected.filter((id) => id !== jobId)
    );
  };

  const [paymentData, setPaymentData] = useState(null);

  useEffect(() => {
    const fetchApplications = async () => {
      try {
        const userToken = localStorage.getItem("accessToken");
        if (!userToken) {
          console.error("No access token found.");
          return;
        }
        const JobId = localStorage.getItem("jobId");
        const response = await axios.get(
          `${
            import.meta.env.VITE_BASE_URL
          }/api/v1/job/my-applications/${JobId}`,
          {
            headers: {
              Authorization: `Bearer ${userToken}`, // Correct header placement
              "Content-Type": "application/json",
            },
          }
        );
        const formattedData = response.data.map((app) => ({
          ...app,
          key: app.id, // Ensures each row has a unique key
        }));
        setTableApplicationDataSources(formattedData);
      } catch (error) {
        console.error("Error fetching applications:", error);
      }
    };
    fetchApplications();
  }, []); // Dependency array ensures it runs once on mount




// Inside NewJobDetails.tsx (adjusted)
const handlePayment = async () => {
  try {
    const token = localStorage.getItem("accessToken");
    if (!token) {
      message.error("User not authenticated");
      return;
    }

    if (selectedJobIds.length === 0) {
      message.warning("Please select at least one job application.");
      return;
    }

    const JobId = id; // useParams id
    const requestData = {
      job_application_ids: selectedJobIds,
      status: "accepted",
    };

    // Step 1 — Request payment initiation from backend
    const response = await axios.patch(
      `${import.meta.env.VITE_BASE_URL}/api/v1/job/my-applications/${JobId}/status/hyper`,
      requestData,
      {
        headers: { Authorization: `Bearer ${token}` },
      }
    );

    const payData = response.data;
    if (!payData.checkoutId) throw new Error("Payment initialization failed");

    // Save ref and show modal
    setCheckoutId(payData.checkoutId);
    localStorage.setItem("subscriptionRef", payData.ref);
    setShowPaymentModal(true);

  } catch (error: any) {
    message.error(
      error?.response?.data?.message || "Payment initialization failed"
    );
  }
};

    /* ---------------- LOAD HYPERPAY WIDGET ---------------- */


    // --- Load HyperPay Widget dynamically ---
    useEffect(() => {
      if (!checkoutId || !showPaymentModal) return;

      const oldScript = document.getElementById("hyperpay-script");
      if (oldScript) oldScript.remove();

      const script = document.createElement("script");
      script.id = "hyperpay-script";
      script.src = `https://test.oppwa.com/v1/paymentWidgets.js?checkoutId=${checkoutId}`;
      script.async = true;
      document.body.appendChild(script);

    }, [checkoutId, showPaymentModal]);

  const handlePaymentCallback = async () => {
  try {
    const token = localStorage.getItem("accessToken");
    if (!token) {
      message.error("User not authenticated");
      return;
    }

    const ref = localStorage.getItem("subscriptionRef");
    if (!ref) return;

    const requestData = { ref };
    const response = await axios.post(
      `${import.meta.env.VITE_BASE_URL}/api/v1/job/my-applications/status/callback/hyper`,
      requestData,
      { headers: { Authorization: `Bearer ${token}` } }
    );

    if (response.status === 200) {
      message.success("Payment successful!");
      localStorage.removeItem("subscriptionRef");
      setShowPaymentModal(false);
    } else {
      message.error("Payment verification failed");
    }
  } catch (error) {
    localStorage.removeItem("subscriptionRef");
    message.error("Failed to verify payment status");
  }
};

  // Run the payment status check after page reload if `ref` exists
  useEffect(() => {
    const ref = localStorage.getItem("subscriptionRef");
    if (ref) {
      handlePaymentCallback();
    }
  }, []);

  const [searchTerm, setSearchTerm] = useState<string>("");
  const [dateRange, setDateRange] = useState<[Dayjs | null, Dayjs | null]>([
    null,
    null,
  ]);
  const [pageSize, setPageSize] = useState(10);
  const [pagination, setPagination] = useState<CustomPagination>({
    limit: pageSize,
    skip: 0,
  });
  const [tableDataSource, setTableDataSource] = useState<DataType[]>([]);
  const [tableApplicationDataSource, setTableApplicationDataSource] = useState<
    ApplicationDataType[]
  >([]);

  const [tableApplicationDataSources, setTableApplicationDataSources] =
    useState<ApplicationDataType[]>([]);
  const [paginatedUsers, setPaginatedUsers] = useState<any[]>([]);
  const [filter, setFilter] = useState<UserCVFilterSchema>({});
  const [selectedRowKeys, setSelectedRowKeys] = useState([]);

  const onSearch = (value: string) => {
    setSearchTerm(value);
    // setPagination((prev) => ({ ...prev, skip: 0 }));
  };

  const onSelectChange = (selectedRowKeys: any) => {
    setSelectedRowKeys(selectedRowKeys);
  };

  const rowSelection = {
    selectedRowKeys,
    onChange: onSelectChange,
    columnWidth: "3%",
    getCheckboxProps: (record: any) => ({
      disabled: record.hasApplied,
    }),
  };
  const onDateRangeChange: RangePickerProps<Dayjs>["onChange"] = (dates) => {
    setDateRange(dates as [Dayjs | null, Dayjs | null]);
  };

  const handlePageSizeChange = (value: number) => {
    setPagination({ ...pagination, limit: value });
    setPageSize(value);
  };

  const handlePaginationChange = (page: number, pageSize?: number) => {
    if (pageSize) {
      setPagination({ limit: pageSize, skip: (page - 1) * pageSize });
    }
  };

  const {
    data: jobData,
    isError: jobIsError,
    isLoading: jobIsLoading,
    mutateAsync,
  } = useJobServiceReadJobPostApiV1JobSinglePost({
    onSuccess: (data) => {
      if (data) setJob(data.data);
      data.data?.job_applications &&
        setHasApplied(
          data.data?.job_applications?.some(
            (application) => application.user_id === userStore.user?.id
          )
        );
    },
    onError: (error, variables, context) => {},
  });

  const {
    data: employeesData,
    isError: employeeIsError,
    isLoading: employeesIsLoading,
    mutateAsync: employeesMutateAsync,
  } = useUserServiceReadManagedUserCvsApiV1UserEmployeesCvPost({
    onSuccess: (data) => {
      if (data) {
        setPaginatedUsers(data.data);
      }
    },
    onError: (error, variables, context) => {},
  });

  const acceptApplication = async (userId: string, detail: string) => {
    const response = await acceptJobApplication
      .mutateAsync({
        requestBody: {
          job_id: parseInt(id!),
          receiver_id: userId,
          detail: detail,
        },
      })
      .then((data) => {
        message.success("Accepted Job Application");
        window.location.reload();
      })
      .catch((error) => {
        message.error(
          error.body?.message || "Failed to accept job application"
        );
      });
  };

  const jobApply = async (userIds: string[]) => {
    const response = await applyForJob
      .mutateAsync({
        requestBody: {
          job_id: job?.id!,
          user_id: userIds,
        },
      })
      .then((data) => {
        message.success("Applied for job successfully!");
        setTimeout(() => {
          window.location.reload();
        }, 1500);
      })
      .catch((error) => {
        message.error(error.body.message || "Job application failed");
      });
  };

  const closeJob = async () => {
    await closeJobPost
      .mutateAsync({
        requestBody: {
          id: parseInt(id!),
        },
      })
      .then((data: any) => {
        message.success("Job post closed successfully!");
        router(-1);
      })
      .catch((error: any) => {
        message.success("Unable to close job post successfully!");
      });
  };

  useEffect(() => {
    mutateAsync({
      requestBody: {
        id: parseInt(id!),
      },
    });
  }, []);

  useEffect(() => {
    const fetchUsers = async () => {
      const formattedStartDate = dateRange[0]?.format("YYYY-MM-DD");
      const formattedEndDate = dateRange[1]?.format("YYYY-MM-DD");

      const response = await employeesMutateAsync({
        limit: pagination.limit,
        skip: pagination.skip,
        search: searchTerm,
        startDate: formattedStartDate,
        endDate: formattedEndDate,
        managerId: userStore.user?.id!,
        requestBody: filter,
      });
    };

    {
      userStore.user?.role !== UserRoleSchema.EMPLOYEE && fetchUsers();
    }
  }, [searchTerm, dateRange, pagination, filter]);

  const handleNavigate = (user_id: string) => {
    navigate(`/${role}/view/employees/${user_id}`);
  };

  const handleCVNavigate = (user_id: string) => {
    navigate(`/${role}/employees/${user_id}`);
  };

  useEffect(() => {
    if (paginatedUsers) {
      const tableData: DataType[] = paginatedUsers.map((employee) => ({
        hasApplied: jobData?.data?.job_applications?.some((application) => {
          return application.user_id === employee.id;
        }),
        Photo:
          employee.cv && employee.cv.head_photo ? (
            <div className="w-10 h-10 rounded-full overflow-hidden">
              <img
                className="w-full h-full object-cover"
                src={`${import.meta.env["VITE_BASE_URL"]}/static/${
                  employee.cv.head_photo
                }`}
                alt="Profile Picture"
              />
            </div>
          ) : (
            <div className="w-10 h-10 rounded-full bg-gray-400"></div>
          ),
        Name: employee.cv
          ? employee.cv?.english_full_name
          : employee.first_name || employee.last_name
          ? employee.first_name + " " + employee.last_name
          : "N/A",
        PassportNumber: employee.cv ? employee.cv.passport_number : "N/A",
        Email:
          employee.cv && employee.cv?.email
            ? employee.cv?.email
            : employee.email
            ? employee.email
            : "N/A",
        PhoneNumber: employee.phone_number?.split(":")[1] || "N/A",
        Status: snakeToCapitalized(employee.status || ""),
        ViewCV: employee.cv ? (
          <button
            className="px-4 py-2 mt-4 bg-blue-600 text-white rounded-lg text-lg font-semibold transition-all duration-300 hover:bg-blue-700"
            onClick={() => handleCVNavigate(employee.cv.user_id)}
          >
            View
          </button>
        ) : (
          <span className="text-gray-500">No CV</span>
        ),

        DownloadCV:
          employee.cv && employee.cv.cv_file ? (
            <a
              href={`${import.meta.env["VITE_BASE_URL"]}/static/${
                employee.cv.cv_file
              }`}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1 text-white bg-blue-500 rounded-md hover:bg-blue-600"
            >
              Download CV
            </a>
          ) : (
            <span className="text-gray-500">No CV</span>
          ),
        User: employee,
      }));

      setTableDataSource(tableData);
    }
  }, [paginatedUsers]);

  useEffect(() => {
    if (jobData?.data?.job_applications) {
      const applications = jobData?.data?.job_applications;
      const tableData: ApplicationDataType[] = applications.map(
        (application) => ({
          Photo:
            application.user?.cv && application.user.cv.head_photo ? (
              <div className="w-10 h-10 rounded-full overflow-hidden">
                <img
                  className="w-full h-full object-cover"
                  src={`${import.meta.env["VITE_BASE_URL"]}/static/${
                    application.user.cv.head_photo
                  }`}
                  alt="Profile Picture"
                />
              </div>
            ) : (
              <div className="w-10 h-10 rounded-full bg-gray-400"></div>
            ),
          Name: application.user?.cv
            ? application.user.cv?.english_full_name
            : application.user?.first_name || application.user?.last_name
            ? application.user?.first_name + " " + application.user?.last_name
            : "N/A",
          Status: snakeToCapitalized(application.status || ""),
          User: application.user!,
          JobApplication: application,
        })
      );

      setTableApplicationDataSource(tableData);
    }
  }, [jobData?.data?.job_applications]);

  return (
    <div className={tw.p_5.h_screen}>
       <ToastContainer />
      {jobIsLoading ? (
        <Spin />
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
            <div>
              <div className={tw.flex.flex_col.space_x_1.mb_8}>
                <span>
                     {/* ---------------- PAYMENT MODAL ---------------- */}


      {showPaymentModal && (
  <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
    <div className="bg-white p-6 rounded-lg shadow-lg w-full max-w-md relative">
      <button
        className="absolute top-2 right-2 text-gray-600 hover:text-black text-xl"
        onClick={() => setShowPaymentModal(false)}
      >
        ✕
      </button>

      <h2 className="text-xl font-semibold text-center mb-4 text-purple-700">
        Complete Your Payment
      </h2>

      <div id="payment-widget-container">
        <form
          action=""
          className="paymentWidgets"
          data-brands="VISA MASTER AMEX"
        ></form>
      </div>
    </div>
  </div>
)}


                  {jobData?.data?.deleted_at ? (
                    <div className="w-fit bg-red-200 text-red-500 p-1 px-4 rounded-md">
                      {t("job_detail_closed")}
                    </div>
                  ) : (
                    <div className="w-fit bg-green-200 text-green-500 p-1 px-4">
                      {t("job_detail_active")}
                    </div>
                  )}
                </span>
                <span className={tw.text_black}>
                  {t("job_detail_posted_on")}:
                  {moment(jobData?.data?.created_at).format("MMM DD, YYYY")}
                </span>
              </div>
              <div
                className={tw.flex.flex_col.space_x_0.space_y_4.justify_start.items_start.mb_10.md(
                  tw.flex.flex_row.space_x_4.space_y_0
                )}
              >
                <div
                  className={
                    tw.w_["260px"].h_["135px"].bg_white.rounded_md.py_6.px_8
                      .shadow.flex.flex_col.space_y_1.items_start.justify_start
                  }
                >
                  <span className={tw.text_gray_500.text_base}>
                    {t("job_detail_number_of_applications")}
                  </span>
                  <span className={tw.text_2xl.font_bold}>
                    {jobData?.data?.job_applications?.length}
                  </span>
                  <div
                    className={tw.flex.flex_row.space_x_1.justify_end.items_end}
                  >
                    <span className={tw.text_sm}>Count </span>
                    <GoTriangleUp className={tw.text_green_500} size={20} />
                    <span className={tw.text_green_500}>0%</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="mb-10">
              <h2 className="text-2xl font-semibold text-black mb-6">
                {t("job_detail_info")}
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-white shadow rounded-xl p-6">
                <div>
                  <p className="text-sm text-black mb-1">
                    {t("job_description")}
                  </p>
                  <p className="text-base font-medium text-black">
                    {jobData?.data?.description || "-"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-black mb-1">{t("job_location")}</p>
                  <p className="text-base font-medium text-black">
                    {jobData?.data?.location || "-"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-black mb-1">
                    {t("job_occupation")}
                  </p>
                  <p className="text-base font-medium text-black capitalize">
                    {jobData?.data?.occupation?.replaceAll("_", " ") || "-"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-black mb-1">
                    {t("job_education")}
                  </p>
                  <p className="text-base font-medium text-black capitalize">
                    {jobData?.data?.education_status?.replaceAll("_", " ") ||
                      "-"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-black mb-1">{t("job_type")}</p>
                  <p className="text-base font-medium text-black capitalize">
                    {jobData?.data?.type?.replaceAll("_", " ") || "-"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-black mb-1">
                    {t("job_vacancies")}
                  </p>
                  <p className="text-base font-medium text-black">
                    {jobData?.data?.amount || "-"}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Job Information Section */}

          {job?.posted_by === userStore.user?.id ? (
            <div className={tw.flex.flex_col.space_x_1.mb_8}>
              <span className={tw.text_2xl.font_semibold.text_primaryBlue}>
                {t("job_detail_applications")}
              </span>
              <div style={{ marginTop: 16, textAlign: "right" }}>
                <Button
                  type="primary"
                  disabled={selectedJobIds.length === 0} // Disable if no items are selected
                  onClick={() => handlePayment(selectedJobIds, setPaymentData)} // Pass selected job IDs
                >
                  Accept
                </Button>
              </div>

              <Table
                columns={applicationColumns}
                dataSource={tableApplicationDataSources}
                scroll={{ x: true }}
              />

              {!jobData?.data?.deleted_at && (
                <div className={tw.flex.w_full.justify_end.mt_8.mb_8.gap_x_2}>
                  <Button
                    className={tw.border_0.bg_primaryBlue.w_[
                      "1/4"
                    ].h_10.rounded_sm.text_white.justify_end.items_end.mt_6.md(
                      tw.mt_0
                    )}
                    onClick={() => router(`/sponsor/jobs/${id}/edit`)}
                  >
                    {t("job_detail_edit")}
                  </Button>
                  <Button
                    className={tw.border_0.bg_red_400.w_[
                      "1/4"
                    ].h_10.rounded_sm.text_white.justify_end.items_end.mt_6.md(
                      tw.mt_0
                    )}
                    onClick={closeJob}
                  >
                    {t("job_detail_close_job_post")}
                  </Button>
                </div>
              )}
            </div>
          ) : userStore.user?.role !== UserRoleSchema.EMPLOYEE &&
            userStore.user?.role !== UserRoleSchema.ADMIN ? (
            <>
              <div
                className={tw.flex_col.space_y_4.space_x_0.justify_between.mb_4.lg(
                  tw.flex.flex_row.space_y_0.space_x_4.mb_4
                )}
              >
                <div className={tw.flex.flex_col.space_y_3.mb_3}>
                  <span className={tw.text_black.font_medium.text_lg}>
                    {t("job_detail_employee")}
                  </span>
                </div>
                <div className={tw.flex.space_x_2.items_center}>
                  <Search
                    placeholder={t("job_detail_passport_number")}
                    allowClear
                    style={{ width: 300 }}
                    onSearch={onSearch}
                  />

                  <UserFilter filter={filter} setFilter={setFilter} />
                  <Button
                    className="px-4 py-2 mt-4 bg-blue-600 text-white rounded-lg text-lg font-semibold transition-all duration-300 hover:bg-blue-700"
                    size="large"
                    onClick={async () => await jobApply(selectedRowKeys)}
                  >{`${t("job_detail_apply")} (${
                    selectedRowKeys.length
                  })`}</Button>
                </div>
              </div>
              {employeesIsLoading ? (
                <Spin />
              ) : (
                <Table
                  rowSelection={rowSelection}
                  columns={columns}
                  dataSource={tableDataSource}
                  scroll={{ x: true }}
                  pagination={{
                    total: employeesData?.count || 0,
                    pageSize: pagination.limit,
                    current: pagination.skip / pagination.limit + 1,
                    onChange: handlePaginationChange,
                  }}
                  rowKey={(record) => record.User.id!}
                />
              )}
              <div className={tw.flex.justify_center}>
                <Select
                  defaultValue={pageSize}
                  style={{ width: 120 }}
                  onChange={handlePageSizeChange}
                >
                  <Option value={10}>10</Option>
                  <Option value={20}>20</Option>
                  <Option value={50}>50</Option>
                  <Option value={100}>100</Option>
                </Select>
              </div>
            </>
          ) : (
            userStore.user.role !== UserRoleSchema.ADMIN && (
              <>
                <Button
                  disabled={hasApplied ? true : false}
                  className="bg-[#1677ff] text-white"
                  size="large"
                  onClick={async () => await jobApply([userStore.user?.id!])}
                >
                  {applyForJob.isLoading ? (
                    <Spin />
                  ) : hasApplied ? (
                    t("job_detail_applied")
                  ) : (
                    t("job_detail_apply")
                  )}
                </Button>
              </>
            )
          )}
        </>
      )}
    </div>
  );
};

export default NewJobDetails;
